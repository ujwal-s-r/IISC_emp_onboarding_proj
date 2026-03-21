import Link from "next/link";

export function GlassNav() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-black/40 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between px-4 sm:px-6">
        <Link
          href="/"
          className="text-sm font-semibold tracking-tight text-white/95 transition hover:text-white"
        >
          AdaptIQ
        </Link>
        <nav className="flex items-center gap-1">
          <Link
            href="/"
            className="rounded-lg px-3 py-1.5 text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            Home
          </Link>
        </nav>
      </div>
    </header>
  );
}
