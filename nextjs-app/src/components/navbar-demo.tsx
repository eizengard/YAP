import { Home, User, Briefcase, FileText, ArrowLeft } from 'lucide-react'
import { NavBar } from "@/components/ui/tubelight-navbar"

export function NavBarDemo() {
  const navItems = [
    { name: 'Home', url: '#home', icon: Home },
    { name: 'About', url: '#about', icon: User },
    { name: 'Projects', url: '#projects', icon: Briefcase },
    { name: 'Resume', url: '#resume', icon: FileText },
    { name: 'Back to YAP', url: 'http://localhost:8080', icon: ArrowLeft }
  ]

  return <NavBar items={navItems} />
} 