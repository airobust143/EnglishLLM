"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)

    // Mock login - in production, this would call your API
    setTimeout(() => {
      setLoading(false)
      // Simulate successful login
      localStorage.setItem("englishApp_user", JSON.stringify({
        email,
        name: email.split("@")[0] || "Student"
      }))
      router.push("/dashboard")
    }, 1000)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-yellow-100 via-orange-50 to-pink-100 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        {/* Header with pencil style */}
        <div className="text-center mb-10">
          <div className="inline-block p-4 rounded-full bg-yellow-200 mb-4 shadow-lg transform -rotate-3">
            <span className="text-4xl">✏️</span>
          </div>
          <h1 className="text-4xl font-bold text-gray-800 mb-2" style={{ fontFamily: 'cursive' }}>
            English Master
          </h1>
          <p className="text-gray-600">Learn English with AI chatbot</p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-3xl shadow-2xl p-8 border-4 border-yellow-200">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Email or Username
              </label>
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all"
                placeholder="enter your email..."
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-pink-500 focus:ring-2 focus:ring-pink-200 outline-none transition-all"
                placeholder="••••••••"
                required
              />
            </div>

            {error && (
              <div className="bg-red-50 border-2 border-red-200 text-red-600 px-4 py-3 rounded-xl">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white font-bold py-4 rounded-xl shadow-lg hover:shadow-xl transform hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-gray-600">
              Don't have an account?{" "}
              <a href="#" className="text-blue-500 font-medium hover:underline">
                Sign up now
              </a>
            </p>
          </div>

          {/* Decorative elements */}
          <div className="mt-8 flex justify-between items-center opacity-50">
            <div className="h-px bg-gray-300 flex-1 mx-2"></div>
            <span className="text-gray-400 text-sm">Hoặc đăng nhập với</span>
            <div className="h-px bg-gray-300 flex-1 mx-2"></div>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-3">
            <button className="flex items-center justify-center py-2 rounded-xl border-2 border-gray-200 hover:bg-gray-50 transition">
              <span className="text-xl">G</span>
            </button>
            <button className="flex items-center justify-center py-2 rounded-xl border-2 border-gray-200 hover:bg-gray-50 transition">
              <span className="text-xl">f</span>
            </button>
            <button className="flex items-center justify-center py-2 rounded-xl border-2 border-gray-200 hover:bg-gray-50 transition">
              <span className="text-xl">in</span>
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-8 text-gray-500 text-sm">
          <p>© 2024 English Master. Learn English every day!</p>
        </div>
      </div>
    </div>
  )
}
