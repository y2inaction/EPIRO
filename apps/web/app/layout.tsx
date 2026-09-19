import type { Metadata } from 'next'
import { Inter } from 'next/font/google'

import { SiteFooter, SiteHeader } from '@/components/Shell'
import '@/styles/globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: {
    default: 'EPIRO',
    template: '%s · EPIRO',
  },
  description:
    'Published evidence, stories and answers, each traceable to the record it rests on.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body
        className={`${inter.className} min-h-screen bg-slate-50 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100`}
      >
        <SiteHeader />
        <main id="main" className="mx-auto max-w-5xl px-4 py-10">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  )
}
