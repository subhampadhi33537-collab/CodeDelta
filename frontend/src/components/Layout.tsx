import { Outlet } from 'react-router-dom'

/**
 * Root layout – wraps every authenticated page.
 * Navigation and global chrome go here in later phases.
 */
export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  )
}
