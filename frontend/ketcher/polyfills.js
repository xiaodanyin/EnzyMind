import process from 'process/browser'

// Ketcher's assert/util dependency expects Node's process API in development.
// Keep the browser implementation confined to the editor's iframe.
window.process = process
