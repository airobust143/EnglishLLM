"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { units } from "../../lib/units"
import CuteStudyCat from "../../components/CuteStudyCat"

type User = { email: string; name: string }

export default function DashboardPage() {
  const router = useRouter()
  const [user] = useState<User | null>(() => {
    if (typeof window === "undefined") return null
    const stored = localStorage.getItem("englishApp_user")
    return stored ? JSON.parse(stored) as User : null
  })

  useEffect(() => {
    if (!localStorage.getItem("englishApp_user")) router.push("/login")
  }, [router])

  const logOut = () => {
    localStorage.removeItem("englishApp_user")
    router.push("/login")
  }

  if (!user) return null

  return (
    <main className="min-h-screen bg-[#f3e7d2] text-[#303b1f]">
      <header className="sticky top-0 z-50 border-b border-[#303b1f]/10 bg-[#f3e7d2]/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#dc3e1d] text-2xl shadow-[3px_3px_0_#303b1f]">🐾</div>
            <div>
              <h1 className="text-xl font-black tracking-tight">Purrfect English</h1>
              <p className="text-xs text-[#303b1f]/60">Welcome, {user.name}</p>
            </div>
          </div>
          <button onClick={logOut} className="rounded-full border border-[#303b1f]/20 px-4 py-2 text-sm font-bold transition hover:border-[#dc3e1d] hover:text-[#dc3e1d]">
            Log out
          </button>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl items-center gap-8 px-5 pb-10 pt-10 lg:grid-cols-[1fr_380px] lg:pt-14">
        <div>
          <p className="mb-4 text-sm font-bold uppercase tracking-[0.24em] text-[#dc3e1d]">Grade 10 guided practice</p>
          <h2 className="max-w-3xl text-5xl font-black leading-none tracking-[-0.05em] md:text-7xl">
            Choose a unit.<br />Practise with purpose.
          </h2>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-[#303b1f]/70">
            Written activities stay organized by unit, while speaking practice can use the complete learning library.
          </p>
        </div>
        <div className="mx-auto w-full max-w-[280px] lg:max-w-none">
          <CuteStudyCat />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-20">
        <div className="mb-8 flex items-end justify-between border-b border-[#303b1f]/15 pb-4">
          <div>
            <h3 className="text-4xl font-black tracking-tight">Units</h3>
            <p className="mt-2 text-[#303b1f]/65">Select written practice or continue by voice.</p>
          </div>
          <span className="hidden text-sm font-bold md:block">3 learning units</span>
        </div>

        <div className="grid gap-7 lg:grid-cols-3">
          {units.map((unit) => (
            <article key={unit.id} className="flex min-h-[390px] flex-col overflow-hidden border-2 border-[#303b1f] bg-[#f8f0e3] shadow-[7px_7px_0_#303b1f]">
              <div className={`${unit.accent} relative min-h-40 p-6 text-white`}>
                <span className="absolute right-5 top-3 text-7xl opacity-30">{unit.icon}</span>
                <p className="text-sm font-black uppercase tracking-[0.2em]">Unit {unit.id}</p>
                <h4 className="relative mt-7 max-w-[85%] text-3xl font-black leading-tight">{unit.shortTitle}</h4>
              </div>
              <div className="flex flex-1 flex-col p-6">
                <p className="leading-7 text-[#303b1f]/70">{unit.description}</p>
                <div className="mt-5 flex gap-2 text-xs font-bold uppercase tracking-wide">
                  <span className="rounded-full bg-[#e8d6b9] px-3 py-1">{unit.level}</span>
                  <span className="rounded-full bg-[#e8d6b9] px-3 py-1">{unit.duration}</span>
                </div>
                <div className="mt-auto grid gap-3 pt-7">
                  <button onClick={() => router.push(`/lesson/${unit.id}`)} className="bg-[#303b1f] px-5 py-3 font-black text-[#f3e7d2] transition hover:bg-[#dc3e1d]">
                    Practice this unit →
                  </button>
                  <button onClick={() => router.push(`/voice-lesson/${unit.id}`)} className="border-2 border-[#303b1f] px-5 py-3 font-black transition hover:bg-[#303b1f] hover:text-[#f3e7d2]">
                    Voice practice
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  )
}
