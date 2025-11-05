import React from 'react'
import { createRoot } from 'react-dom/client'
import { createInertiaApp } from '@inertiajs/react'
import Chat from './pages/Chat'

// Try to get page data from script tag first, then fallback to data attribute
const scriptTag = document.getElementById('page-data')
const appElement = document.getElementById('app')
let initialPage = null

if (scriptTag && scriptTag.textContent) {
  try {
    initialPage = JSON.parse(scriptTag.textContent)
  } catch (e) {
    console.warn('Failed to parse page data from script tag:', e)
  }
}

if (!initialPage && appElement) {
  const pageData = appElement.getAttribute('data-page')
  if (pageData) {
    try {
      initialPage = JSON.parse(pageData)
    } catch (e) {
      console.error('Failed to parse page data from data-page attribute:', e, pageData)
    }
  }
}

createInertiaApp({
  page: initialPage || undefined,
  resolve: (name) => {
    const pages: Record<string, any> = {
      Chat,
    }
    return pages[name]
  },
  setup({ el, App, props }) {
    createRoot(el).render(<App {...props} />)
  },
})


