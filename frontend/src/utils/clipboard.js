/**
 * Copy text to clipboard with fallback for non-HTTPS environments
 * @param {string} text - The text to copy
 * @returns {Promise<boolean>} - Whether the copy was successful
 */
export async function copyToClipboard(text) {
  // Try the modern Clipboard API first
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (err) {
      console.warn('Clipboard API failed, trying fallback:', err)
    }
  }
  
  // Fallback for non-HTTPS or older browsers
  return fallbackCopyToClipboard(text)
}

/**
 * Fallback copy method using execCommand
 * @param {string} text - The text to copy
 * @returns {boolean} - Whether the copy was successful
 */
function fallbackCopyToClipboard(text) {
  const textArea = document.createElement('textarea')
  textArea.value = text
  
  // Avoid scrolling to bottom
  textArea.style.top = '0'
  textArea.style.left = '0'
  textArea.style.position = 'fixed'
  textArea.style.opacity = '0'
  textArea.style.pointerEvents = 'none'
  
  document.body.appendChild(textArea)
  textArea.focus()
  textArea.select()
  
  let success = false
  try {
    success = document.execCommand('copy')
    if (!success) {
      console.warn('execCommand copy failed')
    }
  } catch (err) {
    console.error('Fallback copy failed:', err)
  }
  
  document.body.removeChild(textArea)
  return success
}

export default copyToClipboard
