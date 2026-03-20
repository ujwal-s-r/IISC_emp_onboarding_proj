# Remaining Tasks: Employer Flow

## 1. O*NET Backbone Ingestion (In Progress)
- [x] **Phase 1: Occupations**: Complete ✅.
- [x] **Phase 2a: Tech Nodes**: Complete ✅.
- [ ] **Phase 2b: Tech Relationships**: ~88% Complete 🔄 (~4 minutes remaining).
- [ ] **Phase 2c: Tech Embeddings**: Up next.

## 2. Orchestrator Integration & Testing
- [ ] **Live Normalization Test**: Manually trigger a Role Setup to verify LLM strings (e.g., "Spark") map to O*NET IDs (e.g., `TECH_apache_spark`).
- [ ] **Enrichment Check**: Confirm O*NET "Level" and "Complexity" scores are successfully retrieved and used in the 2D Mastery Matrix.
- [ ] **Persistence**: Verify SQL tables (`TargetSkill`, `TeamRelevanceSignal`) are correctly populated with normalized data.

## 3. Advanced Graph Logic
- [ ] **Dependency Traversal**: Implement Neo4j queries to find "Parent Skills" or prerequisites for high-priority gaps.
- [ ] **Master Skill Library**: Finalize the logic that allows searching the entire O*NET repository from the UI.

## 4. API & UI Readiness
- [ ] **Final Role Report**: Finalize `GET /employer/roles/{id}` to return the enriched 2D Mastery Matrix for the Frontend.
- [ ] **WebSocket Polish**: Ensure real-time updates for "Normalization" and "DB Persistence" phases are smooth.