import './polyfills.js'
import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Editor, InfoModal } from 'ketcher-react'
import { StandaloneStructServiceProvider } from 'ketcher-standalone/dist/binaryWasm'
import 'ketcher-react/dist/index.css'
import './style.css'

// A separate, same-origin document isolates Ketcher's styles, shortcuts and
// React runtime from the Vue application. Indigo runs locally in its worker.
const provider = new StandaloneStructServiceProvider()
function ReactionEditor() {
  const [error, setError] = useState('')
  return React.createElement(React.Fragment, null,
    React.createElement(Editor, {
      structServiceProvider: provider,
      staticResourcesUrl: `${import.meta.env.BASE_URL}ketcher`,
      disableMacromoleculesEditor: true,
      buttons: { miew: { hidden: true }, recognize: { hidden: true }, help: { hidden: true } },
      errorHandler: () => setError('Unable to read this structure. Check the input format and try again.'),
      onInit(ketcher) {
        window.ketcher = ketcher
        window.parent.postMessage({ source: 'enzymind-ketcher', event: 'ready' }, window.location.origin)
      },
    }),
    error ? React.createElement(InfoModal, { message: error, close: () => setError('') }) : null,
  )
}
createRoot(document.getElementById('root')).render(React.createElement(ReactionEditor))
