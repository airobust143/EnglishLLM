export type Unit = {
  id: number
  title: string
  shortTitle: string
  description: string
  topic: string
  level: "Beginner" | "Intermediate"
  duration: string
  icon: string
  accent: string
  vocabulary: string[]
  questions: string[]
}

export const units: Unit[] = [
  {
    id: 1,
    title: "Unit 1: Family Life",
    shortTitle: "Family Life",
    description: "Talk about household chores, family roles, and sharing responsibilities.",
    topic: "Family life and household chores",
    level: "Beginner",
    duration: "20 min",
    icon: "🏠",
    accent: "bg-[#dc3e1d]",
    vocabulary: [
      "household chores",
      "homemaker",
      "breadwinner",
      "do the laundry",
      "do the washing-up",
      "put out the rubbish",
      "shop for groceries",
      "do the heavy lifting",
    ],
    questions: [
      "How does your family divide the household chores?",
      "Which household chore do you usually do, and how often?",
      "Should children help with housework? Why or why not?",
      "Describe one family routine that helps your family feel closer.",
    ],
  },
  {
    id: 2,
    title: "Unit 2: Humans and the Environment",
    shortTitle: "Humans and the Environment",
    description: "Discuss green living, environmental action, and future plans.",
    topic: "Green living and environmental protection",
    level: "Intermediate",
    duration: "25 min",
    icon: "🌱",
    accent: "bg-[#477a45]",
    vocabulary: [
      "carbon footprint",
      "eco-friendly",
      "green lifestyle",
      "raise awareness",
      "clean up",
      "set up a club",
      "reduce waste",
      "protect the environment",
    ],
    questions: [
      "What can students do to make their school greener?",
      "How can you reduce your carbon footprint at home?",
      "What is one environmental activity you are going to join?",
      "Why should people adopt a greener lifestyle?",
    ],
  },
  {
    id: 3,
    title: "Unit 3: Music",
    shortTitle: "Music",
    description: "Talk about artists, musical ability, performances, and sharing music online.",
    topic: "Music and talented artists",
    level: "Intermediate",
    duration: "20 min",
    icon: "🎵",
    accent: "bg-[#7254a3]",
    vocabulary: [
      "pop singer",
      "teen idol",
      "talented artist",
      "musical instrument",
      "perform",
      "cover song",
      "social media",
      "receive an award",
    ],
    questions: [
      "Who is your favourite singer or musician, and why?",
      "Which musical instrument would you like to learn?",
      "How can social media help a young artist become popular?",
      "Describe a talented artist you admire.",
    ],
  },
]

export function getUnit(id: number) {
  return units.find((unit) => unit.id === id)
}
