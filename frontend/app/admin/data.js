export const dashboardStats = {
  today: 128,
  week: 842,
  escalated: 17,
  articles: 64
};

export const dashboardQueriesPerDay = [
  { day: "Mon", value: 120 },
  { day: "Tue", value: 140 },
  { day: "Wed", value: 110 },
  { day: "Thu", value: 160 },
  { day: "Fri", value: 180 },
  { day: "Sat", value: 90 },
  { day: "Sun", value: 70 }
];

export const dashboardEscalationRate = [
  { label: "AI Resolved", value: 82 },
  { label: "Escalated", value: 18 }
];

export const recentQueries = [
  {
    user: "Parent – Grade 4",
    question: "What time does school start tomorrow?",
    status: "Resolved",
    time: "2 min ago"
  },
  {
    user: "Student – Grade 9",
    question: "How do I reset my portal password?",
    status: "Escalated",
    time: "12 min ago"
  },
  {
    user: "Parent – Grade 1",
    question: "Is the bus running during rain?",
    status: "Resolved",
    time: "25 min ago"
  }
];

export const queries = [
  {
    id: "Q-10421",
    user: "Student – Grade 10",
    question: "What topics are on the math exam?",
    response: "The exam covers algebra, geometry, and probability.",
    confidence: 0.92,
    status: "Resolved",
    timestamp: "2026-03-16 10:32"
  },
  {
    id: "Q-10418",
    user: "Parent – Grade 6",
    question: "How do I schedule a meeting with the teacher?",
    response: "You can book via the parent portal under 'Meetings'.",
    confidence: 0.81,
    status: "Pending",
    timestamp: "2026-03-16 09:54"
  },
  {
    id: "Q-10402",
    user: "Student – Grade 8",
    question: "Is there homework in science today?",
    response: "Yes, complete the worksheet on ecosystems.",
    confidence: 0.88,
    status: "Resolved",
    timestamp: "2026-03-15 18:12"
  },
  {
    id: "Q-10397",
    user: "Parent – Grade 3",
    question: "My child has allergies, who should I inform?",
    response: "This query was escalated to the school nurse.",
    confidence: 0.61,
    status: "Escalated",
    timestamp: "2026-03-15 17:40"
  }
];

export const knowledgeArticles = [
  {
    title: "School Start & End Times",
    category: "Logistics",
    updated: "2026-03-10",
    status: "Published"
  },
  {
    title: "Parent Portal Guide",
    category: "Accounts",
    updated: "2026-03-08",
    status: "Published"
  },
  {
    title: "Exam Preparation Tips",
    category: "Academics",
    updated: "2026-02-28",
    status: "Draft"
  }
];

export const escalations = [
  {
    id: "E-902",
    question: "My bus stop changed without notice, what happened?",
    response: "AI could not confirm the route change.",
    admin: "Alex Rivera",
    status: "Open",
    time: "2026-03-16 08:45"
  },
  {
    id: "E-897",
    question: "How do I apply for financial aid?",
    response: "AI suggested generic guidance.",
    admin: "Unassigned",
    status: "Pending",
    time: "2026-03-15 19:12"
  }
];

