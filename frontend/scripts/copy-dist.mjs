import fs from 'node:fs'
import path from 'node:path'

const repoRoot = path.resolve(process.cwd(), '..')
const distDir = path.resolve(process.cwd(), 'dist')
const targetDir = path.resolve(repoRoot, 'backend', 'static', 'frontend')

function rmrf(p) {
  if (!fs.existsSync(p)) return
  for (const entry of fs.readdirSync(p)) {
    const cur = path.join(p, entry)
    const stat = fs.lstatSync(cur)
    if (stat.isDirectory()) rmrf(cur)
    else fs.unlinkSync(cur)
  }
  fs.rmdirSync(p)
}

function copyDir(src, dest) {
  if (!fs.existsSync(dest)) fs.mkdirSync(dest, { recursive: true })
  for (const entry of fs.readdirSync(src)) {
    const s = path.join(src, entry)
    const d = path.join(dest, entry)
    const stat = fs.lstatSync(s)
    if (stat.isDirectory()) copyDir(s, d)
    else fs.copyFileSync(s, d)
  }
}

if (!fs.existsSync(distDir)) {
  console.error('No dist directory found; run vite build first')
  process.exit(1)
}

if (fs.existsSync(targetDir)) rmrf(targetDir)
copyDir(distDir, targetDir)
console.log('Copied dist ->', targetDir)




