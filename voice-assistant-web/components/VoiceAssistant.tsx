"use client"

import useVoiceAssistant from "../hooks/useVoiceAssistant"

export default function VoiceAssistant() {
  const {
    state,
    transcript,
    answer,
    isListening,
    isThinking,
    isSpeaking,
    startListening,
    stop,
  } = useVoiceAssistant()

  const getStatusText = () => {
    switch (state) {
      case "listening":
        return "Listening..."

      case "thinking":
        return "Thinking..."

      case "speaking":
        return "Speaking..."

      default:
        return "Ready"
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
      <div className="w-full max-w-xl">
        {/* Card */}

        <div className="rounded-3xl border border-white/10 bg-white/[0.04] backdrop-blur-xl p-8 shadow-2xl">
          {/* Header */}

          <div className="text-center mb-8">
            <div className="text-sm text-zinc-400 mb-2">
              AI Voice Assistant
            </div>

            <h1 className="text-3xl font-semibold">
              English Conversation
            </h1>

            <p className="text-zinc-500 mt-2">
              Speak naturally with your AI assistant
            </p>
          </div>

          {/* Status */}

          <div className="flex flex-col items-center mb-8">
            <div
              className={`
                w-28
                h-28
                rounded-full
                flex
                items-center
                justify-center
                text-4xl
                transition-all
                duration-300
                ${
                  isListening
                    ? "bg-blue-500/20 ring-4 ring-blue-500/30 scale-110"
                    : isSpeaking
                    ? "bg-green-500/20 ring-4 ring-green-500/30 scale-110"
                    : isThinking
                    ? "bg-yellow-500/20 ring-4 ring-yellow-500/30"
                    : "bg-white/10"
                }
              `}
            >
              {isListening
                ? "🎤"
                : isSpeaking
                ? "🔊"
                : isThinking
                ? "🧠"
                : "🤖"}
            </div>

            <div className="mt-4 text-sm text-zinc-400">
              {getStatusText()}
            </div>
          </div>

          {/* User */}

          <div className="mb-5">
            <div className="text-xs uppercase tracking-wider text-zinc-500 mb-2">
              You
            </div>

            <div className="min-h-[70px] rounded-2xl bg-black/20 border border-white/5 p-4 text-zinc-200">
              {transcript || (
                <span className="text-zinc-600">
                  Say something...
                </span>
              )}
            </div>
          </div>

          {/* Assistant */}

          <div className="mb-8">
            <div className="text-xs uppercase tracking-wider text-zinc-500 mb-2">
              Assistant
            </div>

            <div className="min-h-[100px] rounded-2xl bg-black/20 border border-white/5 p-4 text-zinc-200 leading-relaxed">
              {answer || (
                <span className="text-zinc-600">
                  Your assistant's response will appear here...
                </span>
              )}
            </div>
          </div>

          {/* Controls */}

          <div className="flex justify-center gap-3">
            <button
              onClick={startListening}
              disabled={
                isListening ||
                isThinking ||
                isSpeaking
              }
              className="
                px-6
                py-3
                rounded-full
                bg-white
                text-black
                font-medium
                transition
                hover:bg-zinc-200
                disabled:opacity-40
                disabled:cursor-not-allowed
              "
            >
              🎤 Talk
            </button>

            <button
              onClick={stop}
              className="
                px-6
                py-3
                rounded-full
                bg-white/10
                border
                border-white/10
                text-white
                font-medium
                transition
                hover:bg-white/20
              "
            >
              Stop
            </button>
          </div>
        </div>

        {/* Debug state */}

        <div className="text-center mt-4 text-xs text-zinc-600">
          {state}
        </div>
      </div>
    </main>
  )
}
