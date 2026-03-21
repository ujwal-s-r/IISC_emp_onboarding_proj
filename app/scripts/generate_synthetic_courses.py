"""
generate_synthetic_courses.py
==============================
Generates 120 synthetic AI/ML/DevOps course records using gpt-oss-20b
(no reasoning/CoT), embeds them with NvidiaEmbeddingClient (NemoRetriever
1024-dim), and upserts them into the Qdrant `courses_listed` collection
alongside the real Coursera data.

Usage (from project root, with venv active):
    python -m app.scripts.generate_synthetic_courses

Steps:
  1. 120 seed topic specs covering Python, C++, AI/ML, Gen-AI, Big Data,
     Git/GitHub, Databases, Analytics, DevOps, etc.
  2. gpt-oss-20b generates a realistic JSON course record per seed
     (8 semaphores, incremental save — resumable).
  3. Derive numeric fields (level_score, duration_score, popularity_norm).
  4. Embed each course text via NemoRetriever (passage mode) in batches.
  5. Upsert all valid points into Qdrant 'courses_listed'.
"""

import sys
import os
import json
import re
import uuid
import math
import asyncio
import time
import logging
from pathlib import Path
from datetime import datetime

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from app.config import settings
from app.clients.nvidia_llm_client import nvidia_embedding_client, EMBEDDING_DIM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("gen_synthetic_courses")

# ── Constants ─────────────────────────────────────────────────────────────────
COLLECTION_NAME  = "courses_listed"
EMBED_BATCH_SIZE = 50
MAX_SEMAPHORES   = 8
LLM_MODEL        = "openai/gpt-oss-20b"
NVIDIA_BASE_URL  = "https://integrate.api.nvidia.com/v1"

DATA_DIR    = Path(PROJECT_ROOT) / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = DATA_DIR / "synthetic_courses.jsonl"

DURATION_MAP = {
    "Less Than 2 Hours": 1,
    "1 - 4 Weeks":       2,
    "1 - 3 Months":      3,
    "3 - 6 Months":      4,
}
DURATION_WEEKS = {
    "Less Than 2 Hours": 0.125,
    "1 - 4 Weeks":       2.5,
    "1 - 3 Months":      8.0,
    "3 - 6 Months":      20.0,
}
LEVEL_MAP = {
    "Beginner":     1,
    "Intermediate": 2,
    "Mixed":        2,
    "Advanced":     3,
}
VALID_LEVELS    = set(LEVEL_MAP.keys())
VALID_DURATIONS = set(DURATION_MAP.keys())

# ── 120 Seed Topics ───────────────────────────────────────────────────────────
# Each seed drives one LLM call → one course record.
# Covers every technology area requested.
SEED_TOPICS = [
    # ── Python ────────────────────────────────────────────────────────────────
    {"primary_skill": "Python for Beginners: Syntax, Data Structures & Functions",                   "level": "Beginner",      "subject": "Computer Science"},
    {"primary_skill": "Advanced Python: Decorators, Generators, Async/Await & Metaclasses",          "level": "Advanced",      "subject": "Computer Science"},
    {"primary_skill": "Python Object-Oriented Programming Masterclass",                              "level": "Intermediate",  "subject": "Computer Science"},
    {"primary_skill": "Python for Automation and Scripting with subprocess & schedule",              "level": "Intermediate",  "subject": "Computer Science"},
    {"primary_skill": "Python Testing: pytest, unittest, mocking and coverage",                      "level": "Intermediate",  "subject": "Computer Science"},
    {"primary_skill": "Python Design Patterns, SOLID Principles and Clean Code",                     "level": "Advanced",      "subject": "Computer Science"},
    {"primary_skill": "FastAPI for Building Production-Grade REST APIs with Python",                 "level": "Intermediate",  "subject": "Computer Science"},
    {"primary_skill": "Linux Command Line and Shell Scripting for Data Scientists",                  "level": "Beginner",      "subject": "Computer Science"},
    {"primary_skill": "CUDA Programming for GPU-Accelerated Deep Learning with Python",              "level": "Advanced",      "subject": "Computer Science"},
    # ── C++ ───────────────────────────────────────────────────────────────────
    {"primary_skill": "C++ Fundamentals: Pointers, Memory Management and OOP",                      "level": "Beginner",      "subject": "Computer Science"},
    {"primary_skill": "Modern C++ (C++17/20): STL, Move Semantics, Concurrency and RAII",           "level": "Advanced",      "subject": "Computer Science"},
    {"primary_skill": "C++ for Embedded Systems and High-Performance Computing",                     "level": "Advanced",      "subject": "Computer Science"},
    # ── Java ──────────────────────────────────────────────────────────────────
    {"primary_skill": "Java Programming Essentials: OOP, Collections and Streams",                  "level": "Beginner",      "subject": "Computer Science"},
    {"primary_skill": "Java Spring Boot Microservices and REST API Design",                         "level": "Intermediate",  "subject": "Computer Science"},
    # ── TensorFlow ────────────────────────────────────────────────────────────
    {"primary_skill": "TensorFlow 2.x Deep Learning: Keras, CNNs and Transfer Learning",            "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "Advanced TensorFlow: Custom Models, Training Loops and TF Serving",          "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "TensorFlow Lite for Mobile and Edge AI Deployment",                          "level": "Intermediate",  "subject": "Machine Learning"},
    # ── PyTorch ───────────────────────────────────────────────────────────────
    {"primary_skill": "PyTorch for Deep Learning: Tensors, Autograd and Neural Nets",               "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "PyTorch Lightning, ONNX Export and Production ML Pipelines",                 "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "PyTorch Geometric for Graph Neural Networks",                                "level": "Advanced",      "subject": "Machine Learning"},
    # ── Scikit-learn ──────────────────────────────────────────────────────────
    {"primary_skill": "Scikit-learn for Machine Learning: Classification and Regression",            "level": "Beginner",      "subject": "Machine Learning"},
    {"primary_skill": "Advanced Scikit-learn: Pipelines, Feature Engineering and Ensembles",        "level": "Advanced",      "subject": "Machine Learning"},
    # ── OpenCV ────────────────────────────────────────────────────────────────
    {"primary_skill": "Computer Vision with OpenCV: Image Processing and Object Detection",          "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "OpenCV for Real-Time Video Analysis and Tracking",                            "level": "Intermediate",  "subject": "Machine Learning"},
    # ── NLP ───────────────────────────────────────────────────────────────────
    {"primary_skill": "Natural Language Processing with Python: Tokenization to Transformers",       "level": "Beginner",      "subject": "Machine Learning"},
    {"primary_skill": "Advanced NLP: BERT, RoBERTa and Sequence-to-Sequence Models",                "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Hugging Face Transformers: NLP and Vision Fine-Tuning",                      "level": "Intermediate",  "subject": "Machine Learning"},
    # ── CNNs / RNNs ───────────────────────────────────────────────────────────
    {"primary_skill": "CNNs for Image Classification, Object Detection and Segmentation",            "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "RNNs, LSTMs and GRUs for Sequence Modeling and Time Series",                 "level": "Intermediate",  "subject": "Machine Learning"},
    # ── Model Fine-Tuning: QLoRA / PEFT ──────────────────────────────────────
    {"primary_skill": "Fine-Tuning LLMs with QLoRA: Low-Rank Quantised Adaptation",                 "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "PEFT Techniques: Adapters, LoRA and Prefix Tuning for LLMs",                 "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "End-to-End LLM Fine-Tuning with Hugging Face PEFT and TRL",                  "level": "Advanced",      "subject": "Machine Learning"},
    # ── ML General ────────────────────────────────────────────────────────────
    {"primary_skill": "Introduction to Machine Learning with Python",                               "level": "Beginner",      "subject": "Machine Learning"},
    {"primary_skill": "Deep Learning Specialization: Backpropagation and Optimisation",             "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "MLOps: CI/CD, Model Registry, Monitoring and Kubeflow",                      "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Feature Engineering and Data Preprocessing for ML",                          "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "Hyperparameter Tuning, AutoML and Neural Architecture Search",               "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "Explainable AI: SHAP, LIME and Model Interpretability",                      "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "Bayesian Machine Learning and Probabilistic Programming",                    "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Reinforcement Learning Fundamentals and Deep RL",                            "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Recommender Systems: Collaborative Filtering and Deep Learning",             "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Diffusion Models, VAEs and Generative Image AI",                             "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Speech Recognition and Audio Processing with Deep Learning",                 "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "ML Model Deployment with FastAPI, Docker and Kubernetes",                    "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "Introduction to Statistics and Probability for ML",                          "level": "Beginner",      "subject": "Data Science"},
    {"primary_skill": "Linear Algebra and Calculus for Machine Learning",                           "level": "Beginner",      "subject": "Mathematics"},
    # ── Apache Spark ──────────────────────────────────────────────────────────
    {"primary_skill": "Apache Spark and PySpark for Big Data Processing",                           "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Advanced PySpark: Streaming, MLlib and Delta Lake",                          "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Real-Time Data Streaming with Apache Kafka and Spark",                       "level": "Advanced",      "subject": "Data Engineering"},
    # ── SQL ───────────────────────────────────────────────────────────────────
    {"primary_skill": "SQL for Data Analysis: Fundamentals to Advanced Queries",                    "level": "Beginner",      "subject": "Data Science"},
    {"primary_skill": "Advanced SQL: Window Functions, CTEs and Query Optimisation",                "level": "Advanced",      "subject": "Data Science"},
    # ── Databricks ────────────────────────────────────────────────────────────
    {"primary_skill": "Databricks Lakehouse Platform for Data Engineers",                           "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Databricks MLflow, Model Registry and Experiment Tracking",                  "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "dbt (Data Build Tool) for Analytics Engineering",                            "level": "Intermediate",  "subject": "Data Engineering"},
    # ── Azure ─────────────────────────────────────────────────────────────────
    {"primary_skill": "Azure Data Factory: ETL Pipelines and Cloud Data Integration",               "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Microsoft Azure Cloud Fundamentals (AZ-900) Certification Prep",             "level": "Beginner",      "subject": "Cloud Computing"},
    {"primary_skill": "Azure Machine Learning Service for End-to-End AI Workflows",                 "level": "Advanced",      "subject": "Cloud Computing"},
    {"primary_skill": "Azure Synapse Analytics and Dedicated SQL Pools",                            "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Machine Learning on Google Cloud Vertex AI",                                 "level": "Intermediate",  "subject": "Cloud Computing"},
    {"primary_skill": "AWS SageMaker for ML Model Training, Tuning and Deployment",                 "level": "Intermediate",  "subject": "Cloud Computing"},
    {"primary_skill": "Terraform and Infrastructure-as-Code for ML Platforms",                      "level": "Advanced",      "subject": "Cloud Computing"},
    # ── LangChain ─────────────────────────────────────────────────────────────
    {"primary_skill": "LangChain for LLM Apps: Chains, LCEL, Agents and Memory",                   "level": "Intermediate",  "subject": "Artificial Intelligence"},
    {"primary_skill": "Advanced LangChain: Custom Tools, RAG Pipelines and Evaluation",             "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Building Chatbots and Copilots with LangChain",                              "level": "Intermediate",  "subject": "Artificial Intelligence"},
    # ── LangGraph ─────────────────────────────────────────────────────────────
    {"primary_skill": "LangGraph: Stateful Multi-Agent AI Workflows with Cycles and Branching",     "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Multi-Agent Systems with LangGraph and LangChain",                           "level": "Advanced",      "subject": "Artificial Intelligence"},
    # ── RAG ───────────────────────────────────────────────────────────────────
    {"primary_skill": "Retrieval-Augmented Generation (RAG) from Scratch with Python",              "level": "Intermediate",  "subject": "Artificial Intelligence"},
    {"primary_skill": "Advanced RAG: Hybrid Search, Re-ranking, Chunking and Evaluation",           "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Production RAG Systems: Observability, Guardrails and Scaling",              "level": "Advanced",      "subject": "Artificial Intelligence"},
    # ── Vector Databases ──────────────────────────────────────────────────────
    {"primary_skill": "Vector Databases: Concepts, HNSW Indexing and Similarity Search",            "level": "Intermediate",  "subject": "Artificial Intelligence"},
    {"primary_skill": "Qdrant and Pinecone for Production RAG and Semantic Search",                 "level": "Intermediate",  "subject": "Artificial Intelligence"},
    {"primary_skill": "Embeddings and Semantic Search: From Concept to Production",                 "level": "Intermediate",  "subject": "Artificial Intelligence"},
    # ── Gen-AI General ────────────────────────────────────────────────────────
    {"primary_skill": "Introduction to Generative AI and Large Language Models",                    "level": "Beginner",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Prompt Engineering for ChatGPT, Claude and Open-Source LLMs",               "level": "Beginner",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Building Production-Ready Generative AI Applications",                       "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "LLM Agents: Planning, Tool Use and Multi-Step Reasoning",                    "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "OpenAI API: GPT-4, Assistants, Function Calling and Structured Outputs",    "level": "Intermediate",  "subject": "Artificial Intelligence"},
    {"primary_skill": "LLM Evaluation: Metrics, Benchmarks and Red-Teaming",                       "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Multi-modal AI: Vision-Language Models, CLIP and GPT-4V",                   "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Zero-Shot and Few-Shot Learning Techniques for LLMs",                        "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Responsible AI: Bias Detection, Fairness, Privacy and Safety",               "level": "Intermediate",  "subject": "Artificial Intelligence"},
    # ── PostgreSQL ────────────────────────────────────────────────────────────
    {"primary_skill": "PostgreSQL for Developers: Queries, Indexing and Performance Tuning",        "level": "Intermediate",  "subject": "Databases"},
    {"primary_skill": "Advanced PostgreSQL: Replication, Partitioning and Extensions",              "level": "Advanced",      "subject": "Databases"},
    {"primary_skill": "pgvector: Vector Similarity Search Inside PostgreSQL",                       "level": "Intermediate",  "subject": "Databases"},
    # ── ChromaDB ──────────────────────────────────────────────────────────────
    {"primary_skill": "ChromaDB: Open-Source Vector Database for AI Applications",                  "level": "Intermediate",  "subject": "Databases"},
    # ── MongoDB ───────────────────────────────────────────────────────────────
    {"primary_skill": "MongoDB for Modern Application Development: CRUD to Aggregation",            "level": "Beginner",      "subject": "Databases"},
    {"primary_skill": "Advanced MongoDB: Atlas Search, Change Streams and Vector Search",           "level": "Advanced",      "subject": "Databases"},
    # ── Neo4j ─────────────────────────────────────────────────────────────────
    {"primary_skill": "Neo4j Graph Database: Cypher Queries and Graph Data Modelling",              "level": "Intermediate",  "subject": "Databases"},
    {"primary_skill": "Knowledge Graphs with Neo4j for AI and Recommendation Systems",              "level": "Advanced",      "subject": "Databases"},
    # ── Supabase ──────────────────────────────────────────────────────────────
    {"primary_skill": "Supabase: Open-Source Backend with PostgreSQL, Auth and Storage",            "level": "Beginner",      "subject": "Databases"},
    # ── Other Databases ───────────────────────────────────────────────────────
    {"primary_skill": "Redis for Caching, Pub/Sub and Real-Time Application State",                 "level": "Intermediate",  "subject": "Databases"},
    {"primary_skill": "Elasticsearch for Full-Text Search, Analytics and ELK Stack",                "level": "Intermediate",  "subject": "Databases"},
    # ── Data Analytics & Visualization ────────────────────────────────────────
    {"primary_skill": "Pandas and NumPy for Data Analysis and Manipulation",                        "level": "Beginner",      "subject": "Data Science"},
    {"primary_skill": "Advanced Pandas: Performance, Time Series and Complex Transformations",      "level": "Advanced",      "subject": "Data Science"},
    {"primary_skill": "Matplotlib, Seaborn and Plotly for Data Visualization",                     "level": "Beginner",      "subject": "Data Science"},
    {"primary_skill": "Power BI for Business Intelligence Dashboards",                              "level": "Beginner",      "subject": "Business Intelligence"},
    {"primary_skill": "Advanced Power BI: DAX, Power Query and Enterprise Reporting",               "level": "Advanced",      "subject": "Business Intelligence"},
    {"primary_skill": "Data Cleaning and Preprocessing Best Practices with Python",                 "level": "Intermediate",  "subject": "Data Science"},
    {"primary_skill": "Statistical Analysis and Hypothesis Testing with Python and SciPy",          "level": "Intermediate",  "subject": "Data Science"},
    {"primary_skill": "Exploratory Data Analysis (EDA) for Machine Learning Projects",             "level": "Intermediate",  "subject": "Data Science"},
    {"primary_skill": "Tableau for Data Visualization and Interactive Dashboards",                  "level": "Beginner",      "subject": "Business Intelligence"},
    {"primary_skill": "Time Series Analysis and Forecasting with Machine Learning",                 "level": "Intermediate",  "subject": "Data Science"},
    # ── Git / GitHub / DevOps ─────────────────────────────────────────────────
    {"primary_skill": "Git and GitHub: Version Control from Beginner to Advanced",                  "level": "Beginner",      "subject": "Software Development"},
    {"primary_skill": "Advanced Git: Branching Strategies, Rebasing and Trunk-Based Development",   "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "GitHub Actions: CI/CD Pipelines, Secrets and Workflow Automation",           "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Docker for Developers: Containers, Images, Compose and Networking",          "level": "Beginner",      "subject": "Software Development"},
    {"primary_skill": "Kubernetes for Production: Deployment, Scaling and Observability",           "level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "n8n Workflow Automation: No-Code/Low-Code AI Pipelines",                    "level": "Beginner",      "subject": "Software Development"},
    {"primary_skill": "Data Version Control (DVC) and Experiment Tracking with MLflow",             "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "Microservices Architecture, API Gateways and Service Mesh",                  "level": "Advanced",      "subject": "Software Development"},
    # ── Extra AI / Data Engineering ───────────────────────────────────────────
    {"primary_skill": "Data Pipelines and Orchestration with Apache Airflow",                       "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Introduction to Data Engineering with Python, SQL and Cloud Storage",        "level": "Beginner",      "subject": "Data Engineering"},
    {"primary_skill": "End-to-End MLOps on Kubernetes with Kubeflow and Argo",                     "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Graph Neural Networks for Knowledge Graphs and Link Prediction",             "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "AI for Healthcare: Clinical NLP, EHR Processing and Medical Imaging",       "level": "Advanced",      "subject": "Artificial Intelligence"},

    # ── Batch 2: Software Engineering ──────────────────────────────────────────
    {"primary_skill": "Clean Code and Refactoring: Writing Maintainable Software",                 "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "System Design Interview: Scalable Distributed Systems",                     "level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "REST API Design Best Practices and OpenAPI Specification",                   "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "gRPC and Protocol Buffers for High-Performance Microservices",              "level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "WebSockets, Server-Sent Events and Real-Time API Patterns",                 "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Software Architecture: Hexagonal, CQRS and Event-Sourcing Patterns",       "level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "Domain-Driven Design (DDD) in Practice with Python",                       "level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "GraphQL API Development with Python Strawberry and Ariadne",                "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Concurrency and Parallelism in Python: Threads, Processes, asyncio",        "level": "Advanced",      "subject": "Computer Science"},
    {"primary_skill": "Secure Coding Practices: OWASP Top 10 and Threat Modelling",               "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Observability Engineering: Logs, Metrics, Traces and OpenTelemetry",        "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Service Mesh with Istio: Traffic Management and mTLS",                      "level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "Full-Stack Development with React, FastAPI and PostgreSQL",                  "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "TypeScript and Node.js for Backend API Development",                        "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Rust for Systems Programming: Memory Safety and Concurrency",               "level": "Advanced",      "subject": "Computer Science"},
    {"primary_skill": "Go Programming Language for Scalable Network Services",                     "level": "Intermediate",  "subject": "Computer Science"},
    {"primary_skill": "Event-Driven Architecture with RabbitMQ and Python",                        "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Software Testing Strategies: Unit, Integration and Contract Testing",       "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Performance Engineering: Profiling, Caching and DB Query Tuning",           "level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "OpenAPI, Swagger and API Documentation Best Practices",                     "level": "Beginner",      "subject": "Software Development"},

    # ── Batch 2: SQL & Relational Databases ────────────────────────────────────
    {"primary_skill": "SQL Fundamentals: SELECT, JOINs, GROUP BY and Subqueries",                  "level": "Beginner",      "subject": "Databases"},
    {"primary_skill": "Advanced SQL: Recursive CTEs, JSON Functions and Stored Procedures",        "level": "Advanced",      "subject": "Databases"},
    {"primary_skill": "Database Design: Normalisation, ER Diagrams and Schema Optimisation",       "level": "Intermediate",  "subject": "Databases"},
    {"primary_skill": "PostgreSQL Performance Tuning: EXPLAIN ANALYZE and Index Strategies",       "level": "Advanced",      "subject": "Databases"},
    {"primary_skill": "MySQL for Web Applications: CRUD, Transactions and Replication",            "level": "Beginner",      "subject": "Databases"},
    {"primary_skill": "SQLite for Embedded and Serverless Applications",                           "level": "Beginner",      "subject": "Databases"},
    {"primary_skill": "Data Warehousing Concepts: Star Schema, Kimball and Inmon Methodologies",   "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Analytical SQL: OLAP, Window Functions and Materialized Views",             "level": "Advanced",      "subject": "Data Science"},
    {"primary_skill": "Microsoft SQL Server for Data Professionals: T-SQL and SSMS",               "level": "Intermediate",  "subject": "Databases"},
    {"primary_skill": "Oracle SQL and PL/SQL Fundamentals for Enterprise Developers",              "level": "Intermediate",  "subject": "Databases"},
    {"primary_skill": "Database Migration and Schema Evolution with Flyway and Alembic",           "level": "Intermediate",  "subject": "Databases"},
    {"primary_skill": "Columnar Databases: BigQuery, Redshift and Snowflake for Analytics",        "level": "Intermediate",  "subject": "Data Engineering"},

    # ── Batch 2: Big Data & Streaming ──────────────────────────────────────────
    {"primary_skill": "Apache Kafka Fundamentals: Producers, Consumers and Topics",                "level": "Beginner",      "subject": "Data Engineering"},
    {"primary_skill": "Advanced Kafka: Kafka Streams, ksqlDB and Schema Registry",                 "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Kafka Connect: Building Data Pipelines from Source to Sink",                "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Event Streaming Architectures with Apache Kafka and Flink",                 "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Apache Flink for Stateful Stream Processing at Scale",                      "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Hadoop Ecosystem: HDFS, YARN, Hive and HBase Fundamentals",                "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Delta Lake: ACID Transactions and Time Travel for Big Data",                "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Apache Iceberg and Apache Hudi for Open Table Formats",                     "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Distributed Data Processing with Dask and Ray",                             "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Streaming Analytics: Real-Time Dashboards with Kafka and Grafana",          "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Data Quality and Observability with Great Expectations and Monte Carlo",    "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "ELT vs ETL: Modern Data Stack with dbt, Fivetran and Airbyte",             "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Databricks Unity Catalog: Data Governance and Fine-Grained Access Control","level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Snowflake Data Cloud: Architecture, Sharing and Performance Optimisation",  "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Google BigQuery for Analysts: SQL, Partitioning and ML Integration",        "level": "Intermediate",  "subject": "Data Engineering"},

    # ── Batch 2: Cloud & DevOps ────────────────────────────────────────────────
    {"primary_skill": "Docker Compose and Multi-Container Application Orchestration",              "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Kubernetes Operators and Custom Resource Definitions (CRDs)",               "level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "GitOps with ArgoCD and Flux for Kubernetes Deployments",                   "level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "Prometheus and Grafana for Infrastructure and Application Monitoring",      "level": "Intermediate",  "subject": "Software Development"},
    {"primary_skill": "Azure DevOps: Pipelines, Boards and Artifact Repositories",                 "level": "Intermediate",  "subject": "Cloud Computing"},
    {"primary_skill": "AWS Lambda and Serverless Framework for Event-Driven Python Apps",          "level": "Intermediate",  "subject": "Cloud Computing"},
    {"primary_skill": "GCP Cloud Run and Cloud Functions for Serverless Microservices",            "level": "Intermediate",  "subject": "Cloud Computing"},
    {"primary_skill": "HashiCorp Vault for Secrets Management and PKI",                            "level": "Advanced",      "subject": "Cloud Computing"},
    {"primary_skill": "Site Reliability Engineering (SRE): SLOs, Error Budgets and Incident Mgmt","level": "Advanced",      "subject": "Software Development"},
    {"primary_skill": "Platform Engineering: Internal Developer Platforms with Backstage",         "level": "Advanced",      "subject": "Software Development"},

    # ── Batch 2: AI/ML Extended ────────────────────────────────────────────────
    {"primary_skill": "Federated Learning: Privacy-Preserving Machine Learning at the Edge",      "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Neural Architecture Search and Efficient AI with NAS and EfficientNet",    "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Tabular Deep Learning: TabNet, SAINT and Gradient Boosting Ensembles",     "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "LightGBM and XGBoost for Structured Data Competitions and Production",     "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "Anomaly Detection: Isolation Forests, Autoencoders and Statistical Methods","level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "Active Learning and Human-in-the-Loop ML Pipelines",                       "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Causal Inference and Uplift Modelling for Business Decisions",             "level": "Advanced",      "subject": "Data Science"},
    {"primary_skill": "Survival Analysis and Predictive Maintenance with ML",                     "level": "Intermediate",  "subject": "Data Science"},
    {"primary_skill": "Computer Vision for Manufacturing: Defect Detection and Quality Control",  "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Object Detection with YOLO v8: Training, Fine-Tuning and Deployment",      "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "3D Point Cloud Processing with Open3D and PointNet",                       "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Audio and Speech Synthesis: Whisper, TTS and Voice Cloning",               "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "ML Model Monitoring and Data Drift Detection with Evidently AI",            "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "Quantisation and Pruning for Efficient On-Device AI Inference",            "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "RLHF: Reinforcement Learning from Human Feedback for LLMs",               "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Foundation Models: Pre-Training, Scaling Laws and Emergent Abilities",     "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Vision Transformers (ViT) and DINO for Self-Supervised Visual Learning",  "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "Mixture of Experts (MoE) Architecture for Scalable LLMs",                 "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Synthetic Data Generation for Computer Vision with Unity and Blender",     "level": "Intermediate",  "subject": "Machine Learning"},
    {"primary_skill": "AI Safety, Alignment and Constitutional AI Techniques",                    "level": "Advanced",      "subject": "Artificial Intelligence"},

    # ── Batch 2: Gen-AI Extended ───────────────────────────────────────────────
    {"primary_skill": "Structured Outputs and Function Calling with OpenAI and Mistral APIs",     "level": "Intermediate",  "subject": "Artificial Intelligence"},
    {"primary_skill": "Local LLMs: Ollama, LM Studio and llama.cpp for Private Deployments",     "level": "Intermediate",  "subject": "Artificial Intelligence"},
    {"primary_skill": "CrewAI and AutoGen for Multi-Agent AI Collaboration",                      "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Semantic Kernel for Enterprise AI Orchestration with .NET and Python",     "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "LLM Caching, Rate Limiting and Cost Optimisation in Production",           "level": "Intermediate",  "subject": "Artificial Intelligence"},
    {"primary_skill": "Graph RAG: Knowledge Graph-Enhanced Retrieval for Accurate LLM Answers",   "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Agentic AI: Planning, Memory, Tools and Long-Horizon Task Execution",      "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Fine-Tuning Embedding Models for Domain-Specific Semantic Search",         "level": "Advanced",      "subject": "Machine Learning"},
    {"primary_skill": "LLMOps: Versioning, Testing, Deployment and Monitoring of LLM Apps",      "level": "Advanced",      "subject": "Artificial Intelligence"},
    {"primary_skill": "Building AI Copilots with GitHub Copilot API and VS Code Extensions",      "level": "Advanced",      "subject": "Artificial Intelligence"},

    # ── Batch 2: Analytics & BI ────────────────────────────────────────────────
    {"primary_skill": "Google Looker Studio for Marketing and Business Analytics Dashboards",     "level": "Beginner",      "subject": "Business Intelligence"},
    {"primary_skill": "Metabase and Superset for Open-Source Business Intelligence",              "level": "Beginner",      "subject": "Business Intelligence"},
    {"primary_skill": "Apache Superset: Self-Service Analytics on Big Data Sources",              "level": "Intermediate",  "subject": "Business Intelligence"},
    {"primary_skill": "Product Analytics with Mixpanel, Amplitude and SQL Funnels",              "level": "Intermediate",  "subject": "Business"},
    {"primary_skill": "Growth Analytics: Cohort Analysis, Retention Modelling and LTV",          "level": "Intermediate",  "subject": "Business"},
    {"primary_skill": "Marketing Mix Modelling and Multi-Touch Attribution with Python",          "level": "Advanced",      "subject": "Business"},
    {"primary_skill": "Geospatial Data Analysis with GeoPandas, Kepler.gl and PostGIS",          "level": "Intermediate",  "subject": "Data Science"},
    {"primary_skill": "Monte Carlo Simulations and Risk Modelling with Python",                   "level": "Intermediate",  "subject": "Data Science"},
    {"primary_skill": "A/B Testing at Scale: Sequential Testing, CUPED and Power Analysis",      "level": "Advanced",      "subject": "Data Science"},
    {"primary_skill": "Demand Forecasting with Prophet, NeuralProphet and LightGBM",             "level": "Intermediate",  "subject": "Data Science"},

    # ── Batch 2: Data Engineering Ops ─────────────────────────────────────────
    {"primary_skill": "Apache Airflow 2.x: DAGs, Sensors, XComs and Dynamic Task Mapping",       "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Prefect 2 and Dagster for Modern Python Data Orchestration",              "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Data Contracts: Schema Enforcement and API-First Data Products",           "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "Medallion Architecture: Bronze, Silver, Gold Layers in the Lakehouse",    "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Streaming ETL with Kafka, Flink and ClickHouse for OLAP",                 "level": "Advanced",      "subject": "Data Engineering"},
    {"primary_skill": "ClickHouse for Real-Time Analytical Queries at Petabyte Scale",           "level": "Advanced",      "subject": "Databases"},
    {"primary_skill": "Apache Druid for Sub-Second OLAP on Event-Streaming Data",                "level": "Advanced",      "subject": "Databases"},
    {"primary_skill": "MinIO and Object Storage for On-Premise Data Lakes",                       "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "OpenLineage and Marquez for Data Lineage Tracking",                        "level": "Intermediate",  "subject": "Data Engineering"},
    {"primary_skill": "Apache Nifi for Low-Code Visual Data Routing and Transformation",         "level": "Intermediate",  "subject": "Data Engineering"},
]

# ── LLM Client (gpt-oss-20b, no reasoning/CoT) ────────────────────────────────
_llm_client = AsyncOpenAI(
    api_key=settings.NVIDIA_API_KEY,
    base_url=NVIDIA_BASE_URL,
)

COURSE_SYSTEM = (
    "You are a training-data generator for an online learning catalogue. "
    "Output ONLY a valid JSON object. No explanation, no reasoning traces, no markdown fences. "
    "Respond immediately with the JSON — no preamble whatsoever."
)

COURSE_PROMPT = """\
Generate a realistic online course record for a learning platform.

Topic   : "{primary_skill}"
Level   : {level}
Subject : {subject}

Return ONLY this JSON object — nothing else:
{{
  "title": "<descriptive course title (max 15 words)>",
  "institution": "<realistic provider name>",
  "subject": "{subject}",
  "learning_product": "<one of: Course | Specialization | Professional Certificate | MicroDegree>",
  "level": "{level}",
  "duration_label": "<exactly one of: Less Than 2 Hours | 1 - 4 Weeks | 1 - 3 Months | 3 - 6 Months>",
  "rate": <float between 4.2 and 4.9>,
  "reviews": <integer between 500 and 45000>,
  "skills": [<list of 8-15 specific skill/tool/concept strings covered in this course>]
}}

Rules:
- title: professional and specific to the topic, not generic.
- institution: use real-sounding providers such as DeepLearning.AI, Google, Meta, IBM,
  Microsoft, NVIDIA, AWS, Stanford University, MIT, Duke University, UC San Diego,
  Johns Hopkins, Coursera, DataCamp, Udacy, Fast.ai, Hugging Face — vary them.
- skills: specific technologies, libraries, APIs, or concepts — NOT generic phrases like
  "problem solving". Examples: "PyTorch", "ONNX", "tokenization", "cosine similarity".
- duration_label: Beginner → usually "1 - 4 Weeks" or "1 - 3 Months";
  Advanced → usually "1 - 3 Months" or "3 - 6 Months".
- rate: 4.2–4.9 (one decimal place).
- reviews: 500–45000 (integer).
"""

# ── JSON extractor ─────────────────────────────────────────────────────────────
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)

def _extract_course(raw: str) -> dict | None:
    if not raw:
        return None
    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and "title" in obj and "skills" in obj:
            return obj
    except Exception:
        pass
    m = _OBJ_RE.search(raw)
    if m:
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict) and "title" in obj and "skills" in obj:
                return obj
        except Exception:
            pass
    return None


# ── Async: generate one course per seed ───────────────────────────────────────
async def _generate_one_course(sem: asyncio.Semaphore, seed_idx: int, seed: dict) -> dict:  # noqa: E501
    async with sem:
        try:
            completion = await _llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": COURSE_SYSTEM},
                    {"role": "user",   "content": COURSE_PROMPT.format(**seed)},
                ],
                temperature=0.4,
                stream=False,
                extra_body={"chat_template_kwargs": {"thinking": False}},
            )
            raw = (completion.choices[0].message.content or "").strip()
        except Exception as e:
            log.warning(f"[seed {seed_idx}] LLM call failed: {e}")
            raw = ""

    course = _extract_course(raw)
    return {
        "seed_idx":   seed_idx,
        "seed":       seed,
        "course":     course,
        "status":     "ok" if course else "failed",
        "generated_at": datetime.utcnow().isoformat(),
    }


async def _run_generation(indexed_seeds: list, out_file) -> tuple:
    """indexed_seeds: list of (seed_idx, seed_dict) tuples."""
    sem   = asyncio.Semaphore(MAX_SEMAPHORES)
    tasks = [
        asyncio.ensure_future(_generate_one_course(sem, seed_idx, seed))
        for seed_idx, seed in indexed_seeds
    ]
    ok = fail = 0
    for coro in asyncio.as_completed(tasks):
        record = await coro
        out_file.write(json.dumps(record) + "\n")
        out_file.flush()
        if record["status"] == "ok":
            ok += 1
        else:
            fail += 1
        total = ok + fail
        if total % 10 == 0:
            log.info(f"Progress: {total}/{len(tasks)} | ok={ok} fail={fail}")
    return ok, fail


# ── Derived-field helpers ──────────────────────────────────────────────────────
def _coerce_level(v: str) -> str:
    return v if v in VALID_LEVELS else "Intermediate"

def _coerce_duration(v: str) -> str:
    return v if v in VALID_DURATIONS else "1 - 3 Months"

def _build_payload(course: dict, seed: dict, popularity_norm: float) -> dict:
    level         = _coerce_level(course.get("level", seed["level"]))
    duration_lbl  = _coerce_duration(course.get("duration_label", "1 - 3 Months"))
    rate          = max(4.0, min(5.0, float(course.get("rate", 4.5))))
    reviews       = max(100, int(course.get("reviews", 2000)))
    skills        = [str(s).strip() for s in course.get("skills", []) if str(s).strip()]
    duration_wks  = DURATION_WEEKS[duration_lbl]
    popularity    = round(rate * math.log1p(reviews), 3)

    return {
        "title":            str(course.get("title", "")).strip(),
        "institution":      str(course.get("institution", "")).strip(),
        "subject":          str(course.get("subject", seed["subject"])).strip(),
        "learning_product": str(course.get("learning_product", "Course")).strip(),
        "level":            level,
        "level_score":      LEVEL_MAP[level],
        "duration_label":   duration_lbl,
        "duration_score":   DURATION_MAP[duration_lbl],
        "duration_weeks":   duration_wks,
        "rate":             round(rate, 1),
        "reviews":          reviews,
        "popularity":       popularity,
        "popularity_norm":  popularity_norm,   # filled after normalisation pass
        "skills":           skills,
    }


def _build_embedding_text(payload: dict) -> str:
    """Same format as ingest_courses.py for consistency."""
    return (
        f"Course: {payload['title']}. "
        f"Offered by {payload['institution']}. "
        f"Subject: {payload['subject']}. "
        f"Level: {payload['level']}. "
        f"Skills covered: {', '.join(payload['skills'])}."
    )


# ── Qdrant helpers ─────────────────────────────────────────────────────────────
def _ensure_collection_exists(client: QdrantClient) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME not in existing:
        log.warning(
            f"Collection '{COLLECTION_NAME}' not found. "
            "Run ingest_courses.py first to create and index it. Aborting."
        )
        raise SystemExit(1)
    log.info(f"Collection '{COLLECTION_NAME}' found — will upsert into it.")


def _upsert_batch(
    client: QdrantClient,
    payloads: list[dict],
    vectors:  list[list[float]],
) -> None:
    points = [
        qdrant_models.PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{p['title']}|{p['institution']}")),
            vector=vec,
            payload=p,
        )
        for p, vec in zip(payloads, vectors)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    # ── Step 1: resumability — which seeds already have a result? ─────────────
    done_indices: set[int] = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    done_indices.add(obj["seed_idx"])
                except Exception:
                    pass
        log.info(f"Resuming: {len(done_indices)}/{len(SEED_TOPICS)} seeds already done.")
    else:
        log.info(f"Starting fresh — {len(SEED_TOPICS)} seeds to process.")

    pending = [
        (i, s) for i, s in enumerate(SEED_TOPICS)
        if i not in done_indices
    ]
    log.info(f"Pending: {len(pending)} seeds.")

    # ── Step 2: LLM generation ────────────────────────────────────────────────
    if pending:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
            ok, fail = asyncio.run(_run_generation(
                indexed_seeds=pending,
                out_file=out_f,
            ))
        log.info(f"Generation done. ok={ok}  fail={fail}")
    else:
        log.info("All seeds already processed — skipping LLM phase.")

    # ── Step 3: Load all successful records ──────────────────────────────────
    raw_records = []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if obj.get("status") == "ok" and obj.get("course"):
                    raw_records.append(obj)
            except Exception:
                pass
    log.info(f"Loaded {len(raw_records)} successful course records for embedding + upsert.")

    if not raw_records:
        log.error("No valid records to embed. Check LLM connectivity.")
        return

    # ── Step 4: Build payloads + normalise popularity ─────────────────────────
    # First pass: compute raw popularity for all records
    temp_payloads = []
    for rec in raw_records:
        p = _build_payload(rec["course"], rec["seed"], popularity_norm=0.0)
        temp_payloads.append(p)

    pop_max = max(p["popularity"] for p in temp_payloads) or 1.0
    for p in temp_payloads:
        p["popularity_norm"] = round(p["popularity"] / pop_max, 4)

    # ── Step 5: Embed in batches ──────────────────────────────────────────────
    log.info(f"Embedding {len(temp_payloads)} courses with NemoRetriever (batch={EMBED_BATCH_SIZE})...")
    all_vectors: list[list[float]] = []
    for batch_start in range(0, len(temp_payloads), EMBED_BATCH_SIZE):
        batch_payloads = temp_payloads[batch_start : batch_start + EMBED_BATCH_SIZE]
        texts = [_build_embedding_text(p) for p in batch_payloads]
        try:
            vecs = nvidia_embedding_client.embed_passages(texts)
            all_vectors.extend(vecs)
            log.info(
                f"  Embedded {min(batch_start + EMBED_BATCH_SIZE, len(temp_payloads))}"
                f"/{len(temp_payloads)}"
            )
        except Exception as e:
            log.error(f"Embedding failed for batch {batch_start}: {e}")
            # Insert zero vectors as placeholders so indices stay aligned
            all_vectors.extend([[0.0] * EMBEDDING_DIM] * len(batch_payloads))
        time.sleep(0.3)

    # ── Step 6: Upsert to Qdrant ──────────────────────────────────────────────
    client = QdrantClient(
        url=settings.QDRANT_COURSES_URL,
        api_key=settings.QDRANT_COURSES_API_KEY,
    )
    log.info(f"Connected to Qdrant: {settings.QDRANT_COURSES_URL}")
    _ensure_collection_exists(client)

    upserted = 0
    for batch_start in range(0, len(temp_payloads), EMBED_BATCH_SIZE):
        batch_p = temp_payloads[batch_start : batch_start + EMBED_BATCH_SIZE]
        batch_v = all_vectors[batch_start : batch_start + EMBED_BATCH_SIZE]
        # Skip placeholder zero-vector batches (embedding failed)
        if any(all(x == 0.0 for x in v) for v in batch_v):
            log.warning(f"Skipping batch {batch_start} — zero vectors detected (embedding failed).")
            continue
        try:
            _upsert_batch(client, batch_p, batch_v)
            upserted += len(batch_p)
            log.info(f"  Upserted {upserted}/{len(temp_payloads)}")
        except Exception as e:
            log.error(f"Upsert failed for batch {batch_start}: {e}")
        time.sleep(0.2)

    # ── Final report ──────────────────────────────────────────────────────────
    count = client.count(collection_name=COLLECTION_NAME, exact=True).count
    log.info("=" * 60)
    log.info(f"Done. Upserted {upserted} synthetic courses.")
    log.info(f"Collection '{COLLECTION_NAME}' total points: {count:,}")
    log.info(f"Output JSONL: {OUTPUT_FILE}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
