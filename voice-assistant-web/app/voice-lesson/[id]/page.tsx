"use client"

import { useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import VoiceChat from "../../components/VoiceChat"
import { getUnit } from "../../../lib/units"

export default function VoiceLessonPage() {
  const params = useParams()
  const router = useRouter()
  const unit = getUnit(Number(params.id))

  useEffect(() => {
    if (!localStorage.getItem("englishApp_user")) router.push("/login")
    if (!unit) router.push("/dashboard")
  }, [router, unit])

  if (!unit) return null

  return (
    <main className="min-h-screen bg-[#f3e7d2] text-[#303b1f]">
      <header className="border-b border-[#303b1f]/15">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
          <button onClick={() => router.push("/dashboard")} className="font-bold transition hover:text-[#dc3e1d]">← Back to units</button>
          <div className="text-right">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#dc3e1d]">Voice practice</p>
            <h1 className="text-xl font-black">{unit.title}</h1>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-7 px-5 py-10 lg:grid-cols-[320px_1fr]">
        <aside className="h-fit border-2 border-[#303b1f] bg-[#f8f0e3] p-6 shadow-[6px_6px_0_#303b1f]">
          <div className={`${unit.accent} flex h-16 w-16 items-center justify-center rounded-full text-3xl text-white`}>{unit.icon}</div>
          <h2 className="mt-5 text-3xl font-black">{unit.shortTitle}</h2>
          <p className="mt-3 leading-7 text-[#303b1f]/70">{unit.description}</p>
          <h3 className="mt-7 text-xs font-black uppercase tracking-[0.18em]">Try talking about</h3>
          <ul className="mt-3 space-y-3 text-sm leading-6">
            {unit.questions.map((question) => <li key={question} className="border-l-4 border-[#dc3e1d] pl-3">{question}</li>)}
          </ul>
        </aside>

        <section className="overflow-hidden border-2 border-[#303b1f] bg-white shadow-[7px_7px_0_#303b1f]">
          <VoiceChat unit={unit.id} />
        </section>
      </div>
    </main>
  )
}
