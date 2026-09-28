"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { getUnit } from "../../../lib/units"

const API_URL = process.env.NEXT_PUBLIC_VOICE_API_URL || "http://127.0.0.1:8000"

type Attempt = {
  question: string
  answer: string
  feedback: string
}

export default function LessonPage() {
  const params = useParams()
  const router = useRouter()
  const unit = getUnit(Number(params.id))
  const [questionIndex, setQuestionIndex] = useState(0)
  const [answer, setAnswer] = useState("")
  const [feedback, setFeedback] = useState("")
  const [attempts, setAttempts] = useState<Attempt[]>([])
  const [isChecking, setIsChecking] = useState(false)
  const [showReview, setShowReview] = useState(false)

  useEffect(() => {
    if (!localStorage.getItem("englishApp_user")) router.push("/login")
    if (!unit) router.push("/dashboard")
  }, [router, unit])

  if (!unit) return null

  const currentQuestion = unit.questions[questionIndex]
  const isLastQuestion = questionIndex === unit.questions.length - 1

  const checkAnswer = async () => {
    const learnerAnswer = answer.trim()
    if (!learnerAnswer || isChecking) return

    setIsChecking(true)
    setFeedback("")

    const prompt = [
      `Review a Grade 10 learner's answer for ${unit.title}.`,
      `Question: ${currentQuestion}`,
      `Learner answer: ${learnerAnswer}`,
      "Give one specific strength, correct only the most important mistake, and provide one natural improved answer. Keep it concise and encouraging.",
    ].join("\n")

    let review = "Good effort. Add one clear reason or example to make your answer stronger."

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: prompt,
          provider: "ollama",
          unit: unit.id,
          temperature: 0.2,
          max_tokens: 180,
        }),
      })

      if (!response.ok) throw new Error("Local model unavailable")

      const data = await response.json() as { answer?: string }
      if (data.answer?.trim()) review = data.answer.trim()
    } catch {
      review = "Good effort. Check your verb tense and add one detail from this unit to make the answer more complete."
    }

    setFeedback(review)
    setAttempts((previous) => [
      ...previous.filter((item) => item.question !== currentQuestion),
      { question: currentQuestion, answer: learnerAnswer, feedback: review },
    ])
    setIsChecking(false)
  }

  const continuePractice = () => {
    if (isLastQuestion) {
      setShowReview(true)
      return
    }

    setQuestionIndex((index) => index + 1)
    setAnswer("")
    setFeedback("")
  }

  const restartPractice = () => {
    setQuestionIndex(0)
    setAnswer("")
    setFeedback("")
    setAttempts([])
    setShowReview(false)
  }

  return (
    <main className="min-h-screen bg-[#f3e7d2] text-[#303b1f]">
      <header className="border-b border-[#303b1f]/15 bg-[#f3e7d2]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5">
          <button onClick={() => router.push("/dashboard")} className="font-bold transition hover:text-[#dc3e1d]">← Back to units</button>
          <div className="text-right">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#dc3e1d]">Written practice</p>
            <h1 className="text-xl font-black">{unit.title}</h1>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-5 py-10">
        <div className="mb-8 grid gap-6 lg:grid-cols-[1fr_2fr]">
          <aside className="border-2 border-[#303b1f] bg-[#f8f0e3] p-6 shadow-[6px_6px_0_#303b1f]">
            <div className={`${unit.accent} mb-5 flex h-16 w-16 items-center justify-center rounded-full text-3xl text-white`}>{unit.icon}</div>
            <h2 className="text-3xl font-black leading-tight">{unit.shortTitle}</h2>
            <p className="mt-3 leading-7 text-[#303b1f]/70">{unit.description}</p>

            <div className="mt-7">
              <div className="mb-2 flex justify-between text-xs font-black uppercase tracking-wide">
                <span>Progress</span>
                <span>{attempts.length}/{unit.questions.length}</span>
              </div>
              <div className="h-3 overflow-hidden rounded-full bg-[#e8d6b9]">
                <div className="h-full bg-[#dc3e1d] transition-all" style={{ width: `${(attempts.length / unit.questions.length) * 100}%` }} />
              </div>
            </div>

            <div className="mt-7">
              <h3 className="text-sm font-black uppercase tracking-[0.16em]">Useful words</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {unit.vocabulary.map((word) => (
                  <button key={word} onClick={() => setAnswer((value) => `${value}${value ? " " : ""}${word}`)} className="rounded-full border border-[#303b1f]/25 bg-white px-3 py-1.5 text-sm hover:border-[#dc3e1d]">
                    {word}
                  </button>
                ))}
              </div>
            </div>
          </aside>

          <section>
            {!showReview ? (
              <>
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-sm font-black uppercase tracking-[0.18em] text-[#dc3e1d]">Question {questionIndex + 1} of {unit.questions.length}</p>
                  {attempts.length > 0 && <button onClick={() => setShowReview(true)} className="text-sm font-bold underline">Review practice</button>}
                </div>

                <div className="grid min-h-[340px] border-2 border-[#303b1f] bg-[#303b1f] md:grid-cols-2">
                  <div className="flex flex-col justify-between bg-[#303b1f] p-8 text-[#f3e7d2]">
                    <div>
                      <p className="text-xs font-black uppercase tracking-[0.22em] text-[#f3e7d2]/55">Question</p>
                      <h2 className="mt-6 text-3xl font-black leading-tight">{currentQuestion}</h2>
                    </div>
                    <p className="mt-10 text-sm text-[#f3e7d2]/60">Answer in 2–4 complete English sentences.</p>
                  </div>

                  <div className="flex flex-col bg-white p-8">
                    <label htmlFor="practice-answer" className="text-xs font-black uppercase tracking-[0.22em] text-[#dc3e1d]">Your answer</label>
                    <textarea
                      id="practice-answer"
                      value={answer}
                      onChange={(event) => setAnswer(event.target.value)}
                      placeholder="Write your answer here..."
                      className="mt-5 min-h-48 flex-1 resize-none border-b-2 border-[#303b1f]/25 bg-transparent text-lg leading-8 outline-none focus:border-[#dc3e1d]"
                    />
                    <button onClick={checkAnswer} disabled={!answer.trim() || isChecking} className="mt-6 bg-[#dc3e1d] px-6 py-3 font-black text-white transition hover:bg-[#b93018] disabled:opacity-40">
                      {isChecking ? "Checking with local model..." : "Check my answer"}
                    </button>
                  </div>
                </div>

                {feedback && (
                  <div className="mt-6 border-2 border-[#303b1f] bg-[#e8d6b9] p-6 shadow-[5px_5px_0_#303b1f]">
                    <p className="text-xs font-black uppercase tracking-[0.2em] text-[#dc3e1d]">Tutor feedback</p>
                    <p className="mt-3 whitespace-pre-wrap leading-7">{feedback}</p>
                    <button onClick={continuePractice} className="mt-5 bg-[#303b1f] px-6 py-3 font-black text-[#f3e7d2]">
                      {isLastQuestion ? "Review all practice →" : "Next question →"}
                    </button>
                  </div>
                )}
              </>
            ) : (
              <div>
                <div className="flex flex-wrap items-end justify-between gap-4 border-b-2 border-[#303b1f] pb-5">
                  <div>
                    <p className="text-sm font-black uppercase tracking-[0.2em] text-[#dc3e1d]">Practice review</p>
                    <h2 className="mt-2 text-4xl font-black">Your question & answer board</h2>
                  </div>
                  <button onClick={() => setShowReview(false)} className="border-2 border-[#303b1f] px-5 py-2 font-black">Continue practice</button>
                </div>

                <div className="mt-7 space-y-5">
                  {attempts.length === 0 ? (
                    <p className="border-2 border-dashed border-[#303b1f]/30 p-10 text-center">Complete a question to build your review board.</p>
                  ) : attempts.map((attempt, index) => (
                    <article key={attempt.question} className="grid border-2 border-[#303b1f] md:grid-cols-2">
                      <div className="bg-[#303b1f] p-6 text-[#f3e7d2]">
                        <p className="text-xs font-black uppercase tracking-[0.18em] opacity-60">Question {index + 1}</p>
                        <p className="mt-3 text-xl font-black">{attempt.question}</p>
                      </div>
                      <div className="bg-white p-6">
                        <p className="text-xs font-black uppercase tracking-[0.18em] text-[#dc3e1d]">Your answer</p>
                        <p className="mt-3 leading-7">{attempt.answer}</p>
                        <div className="mt-5 border-l-4 border-[#dc3e1d] bg-[#f3e7d2] p-4 text-sm leading-6">{attempt.feedback}</div>
                      </div>
                    </article>
                  ))}
                </div>

                <button onClick={restartPractice} className="mt-7 bg-[#dc3e1d] px-6 py-3 font-black text-white">Start this unit again</button>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  )
}
