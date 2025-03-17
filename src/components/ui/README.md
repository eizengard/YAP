# Tubelight NavBar Component

A beautiful, animated navigation bar component for Next.js applications with a distinctive "tubelight" effect on the active tab.

## Features

- Responsive design (mobile and desktop layouts)
- Smooth animations using Framer Motion
- Active tab highlighting with a tubelight effect
- Automatic active tab detection based on scroll position
- Smooth scrolling to sections
- Fully customizable with Tailwind CSS

## Installation

This component requires the following dependencies:

```bash
npm install framer-motion lucide-react
```

Make sure you have Tailwind CSS set up in your project.

## Usage

```tsx
import { Home, User, Briefcase, FileText } from 'lucide-react'
import { NavBar } from "@/components/ui/tubelight-navbar"

export function NavBarDemo() {
  const navItems = [
    { name: 'Home', url: '#home', icon: Home },
    { name: 'About', url: '#about', icon: User },
    { name: 'Projects', url: '#projects', icon: Briefcase },
    { name: 'Resume', url: '#resume', icon: FileText }
  ]

  return <NavBar items={navItems} />
}
```

## Props

The NavBar component accepts the following props:

| Prop      | Type                | Description                                |
|-----------|---------------------|--------------------------------------------|
| items     | NavItem[]           | Array of navigation items                  |
| className | string (optional)   | Additional CSS classes for the container   |

### NavItem Interface

```tsx
interface NavItem {
  name: string;    // Display name for the navigation item
  url: string;     // URL or anchor link (e.g., '#home')
  icon: LucideIcon; // Icon from lucide-react
}
```

## Customization

You can customize the appearance of the NavBar by:

1. Passing a `className` prop to override default styles
2. Modifying the component's internal Tailwind classes
3. Adjusting the CSS variables in your global CSS file:

```css
:root {
  --primary: 221.2 83.2% 53.3%;
  --primary-foreground: 210 40% 98%;
  --muted: 210 40% 96.1%;
  --muted-foreground: 215.4 16.3% 46.9%;
  --border: 214.3 31.8% 91.4%;
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
}

.dark {
  --primary: 217.2 91.2% 59.8%;
  --primary-foreground: 222.2 47.4% 11.2%;
  --muted: 217.2 32.6% 17.5%;
  --muted-foreground: 215 20.2% 65.1%;
  --border: 217.2 32.6% 17.5%;
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
}
```

## Responsive Behavior

- On mobile devices (screen width < 768px), the NavBar displays icons only
- On desktop devices (screen width >= 768px), the NavBar displays text labels
- The NavBar is positioned at the bottom of the screen on mobile and at the top on desktop

## Animation Details

The component uses Framer Motion for animations:

- The active tab indicator uses a `layoutId="lamp"` for smooth transitions
- The tubelight effect is created using multiple blurred elements
- Transition settings can be adjusted in the component code:

```tsx
transition={{
  type: "spring",
  stiffness: 300,
  damping: 30,
}}
``` 