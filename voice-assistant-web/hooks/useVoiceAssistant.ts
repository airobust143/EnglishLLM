"use client"

import { useCallback, useEffect, useRef, useState } from "react"

type VoiceState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"

type VoiceProvider = "ollama" | "gemini"
const API_URL =
  process.env.NEXT_PUBLIC_VOICE_API_URL ||
  "http://127.0.0.1:8000"

type SpeechLog = {
  human: string
  assistant: string
  provider: VoiceProvider
  model?: string
  unit?: number
}

export default function useVoiceAssistant(unit?: number) {
  const [state, setState] =
    useState<VoiceState>("idle")

  const [transcript, setTranscript] =
    useState("")

  const [answer, setAnswer] =
    useState("")

  const [availableModels, setAvailableModels] =
    useState<string[]>([])

  const [selectedModel, setSelectedModel] =
    useState("")

  const [provider, setProvider] =
    useState<VoiceProvider>("ollama")

  const [geminiConfigured, setGeminiConfigured] =
    useState<boolean | null>(null)
  // --------------------------------
  // Refs
  // --------------------------------

  const mediaRecorderRef =
    useRef<MediaRecorder | null>(null)

  const mediaStreamRef =
    useRef<MediaStream | null>(null)

  const transcriptRef =
    useRef("")

  const abortControllerRef =
    useRef<AbortController | null>(null)

  const speechQueueRef =
    useRef<string[]>([])

  const speakingRef =
    useRef(false)

  const stoppedRef =
    useRef(false)

  const discardRecordingRef =
    useRef(false)

  const requestInFlightRef =
    useRef(false)

  const sendMessageRef =
    useRef<(text: string) => Promise<void>>(() => Promise.resolve())

  const mountedRef =
    useRef(true)

  const listeningTimeoutRef =
    useRef<ReturnType<typeof setTimeout> | null>(null)

  const silenceTimeoutRef =
    useRef<ReturnType<typeof setTimeout> | null>(null)

  const silenceCheckFrameRef =
    useRef<number | null>(null)

  const audioContextRef =
    useRef<AudioContext | null>(null)

  const hasDetectedSpeechRef =
    useRef(false)

  const listeningStartedAtRef =
    useRef(0)

  const clearSilenceMonitor = useCallback(() => {
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current)
      silenceTimeoutRef.current = null
    }

    if (silenceCheckFrameRef.current !== null) {
      cancelAnimationFrame(silenceCheckFrameRef.current)
      silenceCheckFrameRef.current = null
    }

    void audioContextRef.current?.close()
    audioContextRef.current = null
  }, [])

  useEffect(() => {
    const savedModel = localStorage.getItem("voiceAssistant_model")
    const savedProvider = localStorage.getItem("voiceAssistant_provider")

    if (savedProvider === "ollama" || savedProvider === "gemini") {
      setProvider(savedProvider)
    }

    fetch(`${API_URL}/models`)
      .then((response) => response.json())
      .then((data: {
        models?: string[]
        default?: string
        gemini_configured?: boolean
      }) => {
        const models = data.models || []
        setAvailableModels(models)
        setGeminiConfigured(data.gemini_configured === true)

        const nextModel = savedModel && models.includes(savedModel)
          ? savedModel
          : data.default || models[0] || ""

        setSelectedModel(nextModel)
      })
      .catch(() => {
        setAvailableModels([])
        setGeminiConfigured(null)
      })
  }, [])

  const selectModel = useCallback((model: string) => {
    setSelectedModel(model)
    localStorage.setItem("voiceAssistant_model", model)
  }, [])

  const selectProvider = useCallback((nextProvider: VoiceProvider) => {
    setProvider(nextProvider)
    localStorage.setItem("voiceAssistant_provider", nextProvider)
  }, [])

  // --------------------------------
  // Clean text for TTS
  // --------------------------------

  const cleanForSpeech = useCallback(
    (text: string) => {
      return text
        // Remove markdown
        .replace(/```[\s\S]*?```/g, "")
        .replace(/[*_#>`~-]/g, "")

        // Remove brackets
        .replace(/[()[\]{}]/g, "")

        // Remove repeated whitespace
        .replace(/\s+/g, " ")

        .trim()
    },
    []
  )

  // --------------------------------
  // Cancel current speech
  // --------------------------------

  const cancelSpeech = useCallback(() => {
    if (typeof window === "undefined") {
      return
    }

    window.speechSynthesis.cancel()

    speechQueueRef.current = []

    speakingRef.current = false
  }, [])

  // --------------------------------
  // Start listening
  // --------------------------------

  const startListening = useCallback(() => {
    if (typeof window === "undefined") {
      return
    }

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setAnswer("Local microphone recording is not supported by this browser.")
      return
    }

    console.log("[VOICE] Starting microphone")

    // Cancel old recognition
    try {
      mediaRecorderRef.current?.stop()
    } catch {}

    cancelSpeech()

    transcriptRef.current = ""
    setTranscript("")
    stoppedRef.current = false
    discardRecordingRef.current = false
    hasDetectedSpeechRef.current = false
    listeningStartedAtRef.current = Date.now()
    clearSilenceMonitor()

    void navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => {
        if (stoppedRef.current) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }

        mediaStreamRef.current = stream
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : ""
        const recorder = new MediaRecorder(
          stream,
          mimeType ? { mimeType } : undefined,
        )
        const chunks: Blob[] = []

        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            chunks.push(event.data)
          }
        }

        recorder.onstop = async () => {
          clearSilenceMonitor()
          stream.getTracks().forEach((track) => track.stop())
          mediaStreamRef.current = null
          mediaRecorderRef.current = null

          if (discardRecordingRef.current || chunks.length === 0) {
            setState("idle")
            return
          }

          setState("thinking")

          try {
            const extension = recorder.mimeType.includes("webm") ? "webm" : "mp4"
            const formData = new FormData()
            formData.append(
              "audio",
              new Blob(chunks, { type: recorder.mimeType }),
              `recording.${extension}`,
            )
            const response = await fetch(`${API_URL}/transcribe`, {
              method: "POST",
              body: formData,
            })

            if (!response.ok) {
              const error = await response.json().catch(() => null) as { detail?: string } | null
              throw new Error(error?.detail || "Local transcription failed.")
            }

            const data = await response.json() as { text?: string }
            const text = data.text?.trim() || ""
            if (!text) {
              setAnswer("I could not hear any speech. Please try again.")
              setState("idle")
              return
            }

            transcriptRef.current = text
            setTranscript(text)
            await sendMessageRef.current(text)
          } catch (error) {
            console.error("[VOICE] Local transcription failed:", error)
            setAnswer(error instanceof Error ? error.message : "Local transcription failed.")
            setState("idle")
          }
        }

        mediaRecorderRef.current = recorder
        recorder.start()
        setState("listening")
        console.log("[VOICE] Recording locally")

        try {
          const AudioContextConstructor =
            window.AudioContext ||
            (window as Window & {
              webkitAudioContext?: typeof AudioContext
            }).webkitAudioContext

          if (AudioContextConstructor) {
            const audioContext = new AudioContextConstructor()
            const analyser = audioContext.createAnalyser()
            const source = audioContext.createMediaStreamSource(stream)
            const samples = new Uint8Array(analyser.fftSize)

            analyser.fftSize = 512
            source.connect(analyser)
            audioContextRef.current = audioContext

            const checkForSilence = () => {
              if (mediaRecorderRef.current !== recorder || recorder.state !== "recording") {
                return
              }

              analyser.getByteTimeDomainData(samples)
              let squaredTotal = 0

              for (const sample of samples) {
                const normalized = (sample - 128) / 128
                squaredTotal += normalized * normalized
              }

              const volume = Math.sqrt(squaredTotal / samples.length)
              const elapsed = Date.now() - listeningStartedAtRef.current

              if (volume > 0.035) {
                hasDetectedSpeechRef.current = true
                if (silenceTimeoutRef.current) {
                  clearTimeout(silenceTimeoutRef.current)
                  silenceTimeoutRef.current = null
                }
              } else if (
                hasDetectedSpeechRef.current &&
                !silenceTimeoutRef.current
              ) {
                silenceTimeoutRef.current = setTimeout(() => {
                  silenceTimeoutRef.current = null
                  if (recorder.state === "recording") {
                    recorder.stop()
                  }
                }, 900)
              }

              if (elapsed >= 30000 && recorder.state === "recording") {
                recorder.stop()
                return
              }

              silenceCheckFrameRef.current =
                requestAnimationFrame(checkForSilence)
            }

            silenceCheckFrameRef.current =
              requestAnimationFrame(checkForSilence)
          }
        } catch (error) {
          console.warn("[VOICE] Silence detection unavailable:", error)
        }
      })
      .catch((error: unknown) => {
        console.error("[VOICE] Microphone access failed:", error)
        setAnswer("Microphone access is required for local transcription.")
        setState("idle")
      })
  }, [cancelSpeech, clearSilenceMonitor])

  // --------------------------------
  // TTS queue
  // --------------------------------

  const speakNext = useCallback(() => {
    if (
      typeof window === "undefined"
    ) {
      return
    }

    if (speakingRef.current) {
      return
    }

    const next =
      speechQueueRef.current.shift()

    // Nothing left
    if (!next) {
      console.log(
        "[TTS] Queue empty"
      )

      if (requestInFlightRef.current) {
        setState("thinking")
        return
      }

      setState("idle")

      if (
        !stoppedRef.current
      ) {
        if (
          listeningTimeoutRef.current
        ) {
          clearTimeout(
            listeningTimeoutRef.current
          )
        }

        listeningTimeoutRef.current =
          setTimeout(() => {
            if (
              !stoppedRef.current &&
              mountedRef.current
            ) {
              startListening()
            }
          }, 300)
      }

      return
    }

    const text =
      cleanForSpeech(next)

    if (!text) {
      speakNext()
      return
    }

    console.log(
      "[TTS] Speaking:",
      text
    )

    speakingRef.current = true

    setState("speaking")

    const utterance =
      new SpeechSynthesisUtterance(
        text
      )

    utterance.lang = "en-US"

    utterance.rate = 1.0

    utterance.pitch = 1.0

    utterance.volume = 1.0

    utterance.onstart = () => {
      console.log(
        "[TTS] Started"
      )

      setState("speaking")
    }

    utterance.onend = () => {
      console.log(
        "[TTS] Finished"
      )

      speakingRef.current = false

      // Immediately speak next sentence
      speakNext()
    }

    utterance.onerror = (
      event
    ) => {
      const isExpectedCancellation =
        event.error === "canceled" ||
        event.error === "interrupted"

      if (isExpectedCancellation) {
        console.debug("[TTS] Speech canceled:", event.error)
        speakingRef.current = false
        return
      } else {
        console.error("[TTS] Error:", event.error)
      }

      speakingRef.current = false

      speakNext()
    }

    window.speechSynthesis.speak(
      utterance
    )
  }, [
    cleanForSpeech,
    startListening,
  ])

  // --------------------------------
  // Add sentence to TTS queue
  // --------------------------------

  const enqueueSpeech =
    useCallback(
      (text: string) => {
        const clean =
          cleanForSpeech(text)

        if (!clean) {
          return
        }

        console.log(
          "[TTS] Queue:",
          clean
        )

        speechQueueRef.current.push(
          clean
        )

        // If TTS is idle, start immediately
        if (
          !speakingRef.current
        ) {
          speakNext()
        }
      },
      [
        cleanForSpeech,
        speakNext,
      ]
    )

  // --------------------------------
  // Send message
  // --------------------------------

  const sendMessage =
    useCallback(
      async (text: string) => {
        const message =
          text.trim()

        if (!message) {
          return
        }

        console.log(
          "[VOICE] Sending:",
          message
        )

        setState("thinking")

        setAnswer("")

        cancelSpeech()

        requestInFlightRef.current = true

        let streamCompleted = false

        const controller =
          new AbortController()

        abortControllerRef.current =
          controller

        try {
          const url =
            `${API_URL}/chat/stream`

          console.log(
            "[VOICE] POST:",
            url
          )

          const response =
            await fetch(url, {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
                Accept:
                  "text/plain",
              },

              body: JSON.stringify({
                message,

                provider,

                unit,

                model: provider === "gemini"
                  ? "gemini-3.8-flash"
                  : selectedModel || undefined,

                temperature: 0.2,

                max_tokens: 96,
              }),

              signal:
                controller.signal,
            })

          console.log(
            "[VOICE] HTTP:",
            response.status
          )

          if (!response.ok) {
            const errorText =
              await response.text()

            let errorMessage =
              "The assistant request failed."

            try {
              const errorData = JSON.parse(errorText) as {
                detail?: string
              }

              if (errorData.detail) {
                errorMessage = errorData.detail
              }
            } catch {
              if (errorText) {
                errorMessage = errorText
              }
            }

            throw new Error(
              errorMessage
            )
          }

          if (!response.body) {
            throw new Error("The assistant returned an empty response.")
          }

          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          let fullText = ""
          let sentenceBuffer = ""

          while (true) {
            const { done, value } = await reader.read()

            if (done) {
              break
            }

            const chunk = decoder.decode(value, { stream: true })
            fullText += chunk
            sentenceBuffer += chunk
            setAnswer(fullText)

            const sentenceRegex = /(.+?[.!?](?:\s+|$))/g
            let match
            let lastIndex = 0

            while ((match = sentenceRegex.exec(sentenceBuffer)) !== null) {
              const sentence = match[1].trim()

              if (sentence) {
                enqueueSpeech(sentence)
              }

              lastIndex = sentenceRegex.lastIndex
            }

            sentenceBuffer = sentenceBuffer.slice(lastIndex)
          }

          const finalChunk = decoder.decode()

          if (finalChunk) {
            fullText += finalChunk
            sentenceBuffer += finalChunk
            setAnswer(fullText)
          }

          if (sentenceBuffer.trim()) {
            enqueueSpeech(sentenceBuffer.trim())
          }

          const assistantText = fullText.trim()

          if (assistantText) {
            try {
              const logResponse = await fetch(`${API_URL}/logs/speech`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  human: message,
                  assistant: assistantText,
                  provider,
                  model: provider === "gemini"
                    ? "gemini-3.8-flash"
                    : selectedModel || undefined,
                  unit,
                } satisfies SpeechLog),
              })

              if (!logResponse.ok) {
                const detail = await logResponse.text()
                throw new Error(
                  `Speech log request failed (${logResponse.status}): ${detail}`,
                )
              }
            } catch (error) {
              console.error("[VOICE] Could not save speech log:", error)
            }
          }

          streamCompleted = true

          console.log(
            "[VOICE] Chat complete:",
            fullText
          )

        } catch (error) {
          if (
            error instanceof Error &&
            error.name ===
              "AbortError"
          ) {
            console.log(
              "[VOICE] Request aborted"
            )

            return
          }

          console.error(
            "[VOICE] Request failed:",
            error
          )

          setAnswer(
            error instanceof Error
              ? error.message
              : "Sorry, I could not connect to the assistant."
          )

          setState("idle")
        } finally {
          requestInFlightRef.current = false

          abortControllerRef.current =
            null

          if (
            streamCompleted &&
            !speakingRef.current &&
            speechQueueRef.current.length === 0
          ) {
            speakNext()
          }
        }
      },
      [
        cancelSpeech,
        enqueueSpeech,
        provider,
        selectedModel,
        speakNext,
        unit,
      ]
    )

  // --------------------------------
  // Stop everything
  // --------------------------------

  const stop =
    useCallback(() => {
      console.log(
        "[VOICE] STOP"
      )

      stoppedRef.current =
        true

      clearSilenceMonitor()

      try {
        mediaRecorderRef.current?.stop()
      } catch {}
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
      mediaStreamRef.current = null

      try {
        abortControllerRef.current?.abort()
      } catch {}

      cancelSpeech()

      if (
        listeningTimeoutRef.current
      ) {
        clearTimeout(
          listeningTimeoutRef.current
        )
      }

      setState("idle")
    }, [cancelSpeech, clearSilenceMonitor])

  // --------------------------------
  // Cleanup
  // --------------------------------

  useEffect(() => {
    mountedRef.current = true

    return () => {
      mountedRef.current = false
      discardRecordingRef.current = true
      clearSilenceMonitor()

      try {
        mediaRecorderRef.current?.stop()
      } catch {}
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
      mediaStreamRef.current = null

      try {
        abortControllerRef.current?.abort()
      } catch {}

      if (
        listeningTimeoutRef.current
      ) {
        clearTimeout(
          listeningTimeoutRef.current
        )
      }

      if (
        typeof window !==
        "undefined"
      ) {
        window.speechSynthesis.cancel()
      }

      speechQueueRef.current = []

      speakingRef.current = false
    }
  }, [clearSilenceMonitor])

  sendMessageRef.current = sendMessage

  // --------------------------------
  // Public API
  // --------------------------------

  return {
    state,

    transcript,

    answer,

    isListening:
      state === "listening",

    isThinking:
      state === "thinking",

    isSpeaking:
      state === "speaking",

    startListening,

    availableModels,

    geminiConfigured,
    provider,
    selectProvider,
    selectedModel,

    selectModel,

    sendMessage,

    stop,
  }
}
