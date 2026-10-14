import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <section className="flex flex-col items-center justify-center min-h-screen gap-6 text-center px-6">
      <p className="text-8xl font-black" style={{ color: 'var(--color-accent)' }}>
        404
      </p>
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p style={{ color: 'var(--color-muted)' }}>
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/"
        id="404-home-link"
        className="rounded-xl px-6 py-2.5 text-sm font-semibold text-white"
        style={{ background: 'var(--color-accent)' }}
      >
        Go home
      </Link>
    </section>
  )
}
