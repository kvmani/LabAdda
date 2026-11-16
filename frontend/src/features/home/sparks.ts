export type ResearchSpark = {
  quote: string;
  author: string;
  context?: string;
};

export const RESEARCH_SPARKS: ResearchSpark[] = [
  {
    quote: "Ask the right questions, and nature will open the doors to her secrets.",
    author: "Sir C. V. Raman",
    context: "Nobel Laureate in Physics (1930)",
  },
  {
    quote: "Science is a way of thinking much more than it is a body of knowledge.",
    author: "Carl Sagan",
  },
  {
    quote: "Creativity is seeing what others see and thinking what no one else ever thought.",
    author: "Albert Einstein",
  },
  {
    quote: "Difficulties of the work vanish when you understand that nature does not take leaps.",
    author: "Sir Jagadish Chandra Bose",
    context: "Pioneer in Radio & Plant Physiology",
  },
  {
    quote: "Science knows no country, because knowledge belongs to humanity, and is the torch which illuminates the world.",
    author: "Louis Pasteur",
  },
  {
    quote: "You have to dream before your dreams can come true.",
    author: "Dr. A. P. J. Abdul Kalam",
    context: "Aerospace Scientist & 11th President of India",
  },
  {
    quote: "Nothing in life is to be feared, it is only to be understood. Now is the time to understand more, so that we may fear less.",
    author: "Marie Curie",
    context: "Two-time Nobel Laureate",
  },
  {
    quote: "Nature uses only the longest threads to weave her patterns, so that each small piece reveals the entire tapestry.",
    author: "Richard Feynman",
  },
  {
    quote: "What we observe is not nature itself, but nature exposed to our method of questioning.",
    author: "Werner Heisenberg",
  },
  {
    quote: "In science, the study of some minor anomaly often leads to a completely new realm of discovery.",
    author: "Dr. Homi J. Bhabha",
    context: "Father of Indian Nuclear Research",
  },
  {
    quote: "Equipped with his five senses, man explores the universe around him and calls the adventure Science.",
    author: "Edwin Hubble",
  },
  {
    quote: "He who can listen to the music of the spheres is never alone.",
    author: "Subrahmanyan Chandrasekhar",
    context: "Nobel Laureate in Astrophysics (1983)",
  },
];

const FALLBACK_SPARK: ResearchSpark = {
  quote: "Ask the right questions, and nature will open the doors to her secrets.",
  author: "Sir C. V. Raman",
  context: "Nobel Laureate in Physics (1930)",
};

export function getDailySpark(offset = 0): ResearchSpark {
  const day = new Date().getDate();
  const index = Math.abs(day + offset) % RESEARCH_SPARKS.length;
  return RESEARCH_SPARKS[index] || FALLBACK_SPARK;
}
