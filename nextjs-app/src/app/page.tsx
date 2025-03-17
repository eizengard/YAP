"use client"

import { useEffect, useState } from "react"
import { NavBarDemo } from "@/components/navbar-demo"

export default function Home() {
  const [isEmbedded, setIsEmbedded] = useState(false)

  useEffect(() => {
    // Check if the app is running inside an iframe
    setIsEmbedded(window.self !== window.top)
  }, [])

  return (
    <main className="min-h-screen bg-gradient-to-b from-background to-background/80">
      {/* Hero Section */}
      <section id="home" className="min-h-screen flex flex-col items-center justify-center p-6 text-center">
        <h1 className="text-4xl md:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-primary to-primary/70">
          Welcome to My Portfolio
        </h1>
        <p className="text-xl md:text-2xl max-w-2xl mb-8 text-foreground/80">
          A showcase of my work, skills, and experience as a developer.
          Built with Next.js, Tailwind CSS, and the Tubelight NavBar component.
        </p>
        <div className="flex flex-col sm:flex-row gap-4">
          <a 
            href="#projects" 
            className="px-6 py-3 bg-primary text-primary-foreground rounded-full font-medium hover:bg-primary/90 transition-colors"
          >
            View Projects
          </a>
          <a 
            href="#about" 
            className="px-6 py-3 bg-muted text-foreground rounded-full font-medium hover:bg-muted/90 transition-colors"
          >
            About Me
          </a>
        </div>
      </section>

      {/* About Section */}
      <section id="about" className="min-h-screen flex flex-col items-center justify-center p-6 py-24">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold mb-8 text-center">About Me</h2>
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="aspect-square rounded-full overflow-hidden bg-muted flex items-center justify-center">
              <div className="text-6xl">👨‍💻</div>
            </div>
            <div>
              <h3 className="text-2xl font-semibold mb-4">Hi, I&apos;m John Doe</h3>
              <p className="text-foreground/80 mb-4">
                I&apos;m a full-stack developer with a passion for creating beautiful, 
                functional, and user-friendly websites and applications.
              </p>
              <p className="text-foreground/80 mb-4">
                With over 5 years of experience in web development, I specialize in 
                React, Next.js, Node.js, and TypeScript.
              </p>
              <div className="flex flex-wrap gap-2 mt-6">
                <span className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">React</span>
                <span className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">Next.js</span>
                <span className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">TypeScript</span>
                <span className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">Node.js</span>
                <span className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">Tailwind CSS</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Projects Section */}
      <section id="projects" className="min-h-screen flex flex-col items-center justify-center p-6 py-24 bg-muted/5">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold mb-12 text-center">My Projects</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-card rounded-lg overflow-hidden border border-border hover:border-primary/50 transition-colors">
                <div className="aspect-video bg-muted flex items-center justify-center">
                  <span className="text-4xl">🚀</span>
                </div>
                <div className="p-6">
                  <h3 className="text-xl font-semibold mb-2">Project {i}</h3>
                  <p className="text-foreground/70 mb-4">
                    A description of this amazing project and the technologies used to build it.
                  </p>
                  <div className="flex flex-wrap gap-2 mb-4">
                    <span className="px-2 py-1 bg-primary/10 text-primary rounded-full text-xs">React</span>
                    <span className="px-2 py-1 bg-primary/10 text-primary rounded-full text-xs">Next.js</span>
                    <span className="px-2 py-1 bg-primary/10 text-primary rounded-full text-xs">TypeScript</span>
                  </div>
                  <a 
                    href="#" 
                    className="text-primary hover:text-primary/80 font-medium text-sm flex items-center gap-1"
                  >
                    View Project
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14"></path>
                      <path d="m12 5 7 7-7 7"></path>
                    </svg>
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Resume Section */}
      <section id="resume" className="min-h-screen flex flex-col items-center justify-center p-6 py-24">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold mb-12 text-center">Resume</h2>
          
          <div className="mb-12">
            <h3 className="text-2xl font-semibold mb-6 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="18" x="3" y="4" rx="2" ry="2"></rect>
                <line x1="16" x2="16" y1="2" y2="6"></line>
                <line x1="8" x2="8" y1="2" y2="6"></line>
                <line x1="3" x2="21" y1="10" y2="10"></line>
              </svg>
              Experience
            </h3>
            <div className="space-y-8">
              <div className="border-l-2 border-primary/30 pl-6 relative">
                <div className="absolute w-3 h-3 bg-primary rounded-full -left-[7px] top-1"></div>
                <h4 className="text-xl font-medium">Senior Frontend Developer</h4>
                <p className="text-foreground/70">Tech Company Inc. • 2020 - Present</p>
                <ul className="mt-4 space-y-2 text-foreground/80">
                  <li>Led the development of the company&apos;s main product using React and TypeScript</li>
                  <li>Implemented a new design system that improved development speed by 30%</li>
                  <li>Mentored junior developers and conducted code reviews</li>
                </ul>
              </div>
              <div className="border-l-2 border-primary/30 pl-6 relative">
                <div className="absolute w-3 h-3 bg-primary rounded-full -left-[7px] top-1"></div>
                <h4 className="text-xl font-medium">Frontend Developer</h4>
                <p className="text-foreground/70">Web Solutions LLC • 2018 - 2020</p>
                <ul className="mt-4 space-y-2 text-foreground/80">
                  <li>Developed responsive web applications using React and Redux</li>
                  <li>Collaborated with designers to implement pixel-perfect UIs</li>
                  <li>Optimized application performance and loading times</li>
                </ul>
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="text-2xl font-semibold mb-6 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z"></path>
                <path d="M6 12v5c3 3 9 3 12 0v-5"></path>
              </svg>
              Education
            </h3>
            <div className="space-y-8">
              <div className="border-l-2 border-primary/30 pl-6 relative">
                <div className="absolute w-3 h-3 bg-primary rounded-full -left-[7px] top-1"></div>
                <h4 className="text-xl font-medium">Bachelor of Science in Computer Science</h4>
                <p className="text-foreground/70">University of Technology • 2014 - 2018</p>
                <p className="mt-4 text-foreground/80">
                  Graduated with honors. Specialized in web development and software engineering.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 text-center text-foreground/60">
        <p>© 2024 John Doe. All rights reserved.</p>
      </footer>

      {/* Add the NavBarDemo component only when not embedded */}
      {!isEmbedded && <NavBarDemo />}
    </main>
  )
}
