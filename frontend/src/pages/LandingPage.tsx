import { Link } from 'react-router-dom'

/**
 * Landing page – placeholder until Phase 11 builder UI.
 * Verifies routing and Tailwind are working.
 */
export default function LandingPage() {
  return (
    <section className="flex flex-col items-center justify-center min-h-screen px-6 text-center">
      {/* Glow blob */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div
          className="absolute left-1/2 top-1/3 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full opacity-20 blur-3xl"
          style={{ background: 'radial-gradient(circle, #7c6af7 0%, transparent 70%)' }}
        />
      </div>

      <div className="relative z-10 max-w-2xl">
        {/* Badge */}
        <span
          className="inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs font-medium mb-8"
          style={{
            borderColor: 'var(--color-border)',
            color: 'var(--color-accent)',
            background: 'rgba(124,106,247,0.08)',
          }}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
          Phase 0 — Foundation
        </span>

        <h1
          className="text-5xl sm:text-7xl font-extrabold tracking-tight leading-none mb-6"
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Code
          <span style={{ color: 'var(--color-accent)' }}>Delta</span>
        </h1>

        <p className="text-lg sm:text-xl mb-10" style={{ color: 'var(--color-muted)' }}>
          Describe a website. Watch a team of AI agents plan, design, code,
          review and ship it — live.
        </p>

        <div className="flex flex-wrap gap-4 justify-center">
          <Link
            to="/register"
            id="cta-register"
            className="rounded-xl px-8 py-3.5 text-sm font-semibold text-white transition-all duration-200 hover:scale-105 hover:brightness-110"
            style={{ background: 'var(--color-accent)' }}
          >
            Get started free
          </Link>
          <Link
            to="/login"
            id="cta-login"
            className="rounded-xl px-8 py-3.5 text-sm font-semibold border transition-all duration-200 hover:scale-105"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-muted)',
            }}
          >
            Sign in
          </Link>
        </div>
      </div>
    </section>
  )
}
