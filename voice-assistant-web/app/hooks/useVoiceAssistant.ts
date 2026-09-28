import { useState, useEffect, useRef } from "react"

type VoiceState = "ready" | "listening" | "thinking" | "speaking"

interface UseVoiceAssistantReturn {
  state: VoiceState
  transcript: string
  answer: string
  isListening: boolean
  isThinking: boolean
  isSpeaking: boolean
  startListening: () => void
  stop: () => void
}

export default function useVoiceAssistant(): UseVoiceAssistantReturn {
  const [state, setState] = useState<VoiceState>("ready")
  const [transcript, setTranscript] = useState("")
  const [answer, setAnswer] = useState("")
  const [isListening, setIsListening] = useState(false)
  const [isThinking, setIsThinking] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  
  const recognitionRef = useRef<any>(null)
  const synthRef = useRef<SpeechSynthesis | null>(null)

  useEffect(() => {
    // Initialize Speech Recognition
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition()
      recognitionRef.current.continuous = false
      recognitionRef.current.lang = "en-US"
      recognitionRef.current.interimResults = false

      recognitionRef.current.onstart = () => {
        setIsListening(true)
        setState("listening")
      }

      recognitionRef.current.onend = () => {
        setIsListening(false)
        if (state === "listening") {
          setState("ready")
        }
      }

      recognitionRef.current.onresult = (event: any) => {
        const last = event.results.length - 1
        const text = event.results[last][0].transcript
        setTranscript(text)
        handleUserMessage(text)
      }

      recognitionRef.current.onerror = (event: any) => {
        console.error("Speech recognition error", event.error)
        setIsListening(false)
        setState("ready")
      }
    }

    // Initialize Speech Synthesis
    synthRef.current = window.speechSynthesis

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
      if (synthRef.current) {
        synthRef.current.cancel()
      }
    }
  }, [state])

  const handleUserMessage = async (message: string) => {
    setIsThinking(true)
    setState("thinking")

    // Simulate AI response
    setTimeout(() => {
      let responseText = ""
      
      if (message.toLowerCase().includes("hello") || message.toLowerCase().includes("hi")) {
        responseText = "Hello! How are you today? Would you like to practice some English conversation?"
      } else if (message.toLowerCase().includes("good") || message.toLowerCase().includes("fine")) {
        responseText = "That's great to hear! Let's continue practicing. What would you like to talk about?"
      } else if (message.toLowerCase().includes("thank")) {
        responseText = "You're welcome! Keep practicing and you'll improve quickly."
      } else {
        responseText = `That's interesting! You said: "${message}". Can you tell me more about that in English?`
      }

      setAnswer(responseText)
      speakResponse(responseText)
      setIsThinking(false)
      setState("speaking")
    }, 1500)
  }

  const speakResponse = (text: string) => {
    if (!synthRef.current) return

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = "en-US"
    utterance.rate = 1
    utterance.pitch = 1

    utterance.onend = () => {
      setIsSpeaking(false)
      setState("ready")
    }

    utterance.onerror = () => {
      setIsSpeaking(false)
      setState("ready")
    }

    synthRef.current.speak(utterance)
  }

  const startListening = () => {
    if (recognitionRef.current && state !== "listening") {
      setTranscript("")
      setAnswer("")
      recognitionRef.current.start()
    }
  }

  const stop = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
    }
    if (synthRef.current) {
      synthRef.current.cancel()
    }
    setIsListening(false)
    setIsThinking(false)
    setIsSpeaking(false)
    setState("ready")
  }

  return {
    state,
    transcript,
    answer,
    isListening,
    isThinking,
    isSpeaking,
    startListening,
    stop
  }
}
