"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

export default function Home() {
  const router = useRouter()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    const storedUser = localStorage.getItem("englishApp_user")
    if (storedUser) {
      router.push("/dashboard")
    } else {
      router.push("/login")
    }
  }, [router])

  if (checking) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-yellow-100 via-orange-50 to-pink-100 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block p-4 rounded-full bg-yellow-200 mb-4">
            <span className="text-4xl">⏳</span>
          </div>
          <p className="text-gray-600 text-lg">Checking...</p>
        </div>
      </div>
    )
  }

  return null
}
