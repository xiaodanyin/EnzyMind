<template>
  <div ref="shell" class="ketcher-editor" :class="{ 'is-expanded': expanded }">
    <div class="ketcher-toolbar">
      <span class="ketcher-brand"><i class="bi bi-bezier2" aria-hidden="true"></i> Ketcher <span>{{ mode === 'reaction' ? 'Reaction editor' : 'Molecule editor' }}</span></span>
      <button type="button" class="ketcher-expand" :aria-label="expanded ? 'Exit full screen editor' : 'Expand reaction editor'" :disabled="!ready" @click="toggleExpanded">
        <i :class="expanded ? 'bi bi-fullscreen-exit' : 'bi bi-arrows-fullscreen'" aria-hidden="true"></i><span>{{ expanded ? 'Exit full screen' : 'Expand' }}</span>
      </button>
    </div>
    <div class="ketcher-frame-shell" :aria-busy="!ready || importing">
      <iframe ref="frame" :key="attempt" :src="editorUrl" :title="`Ketcher ${mode} editor`" allow="clipboard-write" @load="connect" @error="failLoading"></iframe>
      <div v-if="!ready || importing || disabled" class="ketcher-overlay" role="status">
        <template v-if="loadError">
          <i class="bi bi-exclamation-circle" aria-hidden="true"></i>
          <p>Ketcher could not load. You can still enter SMILES below.</p>
          <button type="button" class="btn btn-outline-custom btn-sm" @click="retry">Retry editor</button>
        </template>
        <template v-else><span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>{{ disabled ? 'Preparing prediction…' : importing ? 'Updating drawing…' : 'Loading Ketcher…' }}</span></template>
      </div>
    </div>
    <p v-if="syncError" class="ketcher-message" role="status"><i class="bi bi-info-circle" aria-hidden="true"></i> {{ syncError }}</p>
    <div class="ketcher-footer"><span>{{ mode === 'reaction' ? 'Draw reactants, a reaction arrow, and products.' : 'Draw your substrate molecule. Atom labels and stereochemistry are preserved.' }}</span><span v-if="ready" class="ketcher-sync" role="status">{{ syncing ? 'Syncing SMILES…' : 'SMILES linked' }}</span></div>
  </div>
</template>

<script>
import { validateChemical } from '@/utils/proteinInput'
import { drawingSmiles } from '@/utils/ketcherSmiles'

export default {
  name: 'KetcherEditor',
  props: { modelValue: { type: String, default: '' }, mode: {type: String, default: 'molecule'}, disabled: Boolean },
  emits: ['update:modelValue'],
  data() {
    return { ready: false, loadError: false, syncError: '', syncing: false, importing: false, expanded: false, attempt: 0 }
  },
  computed: { editorUrl() { return `${import.meta.env.BASE_URL}ketcher/index.html` } },
  created() {
    this._queue = Promise.resolve()
    this._revision = 0
    this._source = 'text'
  },
  mounted() {
    window.addEventListener('message', this.onMessage)
    document.addEventListener('fullscreenchange', this.onFullscreenChange)
    this._resizeObserver = new ResizeObserver(() => {
      clearTimeout(this._fitTimer)
      this._fitTimer = setTimeout(this.fitDrawing, 120)
    })
    this._resizeObserver.observe(this.$refs.shell)
    this.armLoadTimeout()
  },
  beforeUnmount() {
    this._disposed = true
    this._revision++
    clearTimeout(this._syncTimer)
    clearTimeout(this._loadTimer)
    clearTimeout(this._fitTimer)
    this._resizeObserver?.disconnect()
    this.disconnect()
    window.removeEventListener('message', this.onMessage)
    document.removeEventListener('fullscreenchange', this.onFullscreenChange)
    if (document.fullscreenElement === this.$refs.shell) document.exitFullscreen().catch(() => {})
  },
  watch: {
    modelValue(value) {
      const fromDrawing = value === this._echo
      this._echo = null
      if (fromDrawing) return
      this._source = 'text'
      const revision = ++this._revision
      this.syncError = ''
      clearTimeout(this._syncTimer)
      if (this.ready) {
        this.syncing = true
        this._syncTimer = setTimeout(() => this.importText(value, revision), 350)
      }
    },
  },
  methods: {
    armLoadTimeout() {
      clearTimeout(this._loadTimer)
      this._loadTimer = setTimeout(this.failLoading, 45000)
    },
    onMessage(event) {
      if (event.origin !== window.location.origin || event.source !== this.$refs.frame?.contentWindow) return
      if (event.data?.source === 'enzymind-ketcher' && event.data.event === 'ready') this.connect()
      if (event.data?.source === 'enzymind-ketcher' && event.data.event === 'load-error') this.failLoading()
    },
    connect() {
      if (this.ready || this._disposed) return
      const ketcher = this.$refs.frame?.contentWindow?.ketcher
      if (!ketcher) return // The frame load event can precede Indigo initialization.
      this._ketcher = ketcher
      this._subscription = ketcher.editor.subscribe('change', this.onDrawingChange)
      clearTimeout(this._loadTimer)
      this.ready = true
      this.loadError = false
      this.importText(this.modelValue, this._revision)
    },
    disconnect() {
      if (this._subscription && this._ketcher) this._ketcher.editor.unsubscribe('change', this._subscription)
      this._subscription = null
      this._ketcher = null
    },
    failLoading() { if (!this.ready && !this._disposed) this.loadError = true },
    retry() {
      this._revision++
      this.disconnect()
      this.ready = false
      this.loadError = false
      this.attempt++
      this.armLoadTimeout()
    },
    enqueue(work) {
      const operation = this._queue.then(() => this._disposed ? undefined : work())
      this._queue = operation.catch(() => {})
      return operation
    },
    importText(value, revision) {
      return this.enqueue(async () => {
        if (revision !== this._revision || !this._ketcher) return
        this.importing = true
        try {
          if (value.trim()) {
            // Ketcher 3.18 reports failed imports through its event bus; its
            // setMolecule promise resolves even when parsing fails.
            let failed = false
            const onFailure = () => { failed = true }
            const ketcher = this._ketcher
            ketcher.eventBus.on('FAILURE', onFailure)
            try { await ketcher.setMolecule(value.trim()) }
            finally { ketcher.eventBus.removeListener('FAILURE', onFailure) }
            if (failed) throw new Error('Invalid structure input')
          } else this._ketcher.editor.clear()
          if (revision === this._revision) this.syncError = ''
        } catch {
          if (revision === this._revision) this.syncError = 'The drawing could not be updated. Your typed SMILES is preserved; finish or correct the text below.'
        } finally {
          this.importing = false
          if (revision === this._revision) {
            this.syncing = false
            this.fitDrawing()
          }
        }
      })
    },
    onDrawingChange() {
      if (this.importing || this._disposed) return
      this._source = 'canvas'
      const revision = ++this._revision
      clearTimeout(this._syncTimer)
      this.syncing = true
      this._syncTimer = setTimeout(() => this.exportDrawing(revision).catch(() => {}), 120)
    },
    exportDrawing(revision) {
      return this.enqueue(async () => {
        if (revision !== this._revision || !this._ketcher) return
        try {
          // Plain SMILES retains atom maps, isotopes, charge and stereochemistry.
          // Do not strip bracketed atom information with a regular expression.
          const smiles = await drawingSmiles(this._ketcher)
          if (revision !== this._revision || this._disposed) return
          this._echo = smiles
          this.$emit('update:modelValue', smiles)
          this.syncError = ''
          return smiles
        } catch {
          if (revision === this._revision) this.syncError = 'The drawing could not be converted to SMILES. Check the reaction or enter its SMILES below.'
          throw new Error('Unable to read the reaction drawing. Correct it or enter Reaction SMILES before submitting.')
        } finally {
          if (revision === this._revision) this.syncing = false
        }
      })
    },
    clear() {
      clearTimeout(this._syncTimer)
      this._source = 'text'
      const revision = ++this._revision
      this._echo = ''
      this.syncError = ''
      this.$emit('update:modelValue', '')
      if (this.ready) return this.importText('', revision)
    },
    async getSmilesForSubmission() {
      clearTimeout(this._syncTimer)
      // Read the last canvas edit immediately, even if its debounce has not fired.
      // Typed text remains authoritative when it cannot yet be imported.
      let smiles
      while (this._source === 'canvas' && this.ready && !this._disposed) {
        const revision = this._revision
        smiles = await this.exportDrawing(revision)
        if (revision === this._revision) break
      }
      if (this._source === 'text') {
        if (this.ready && this.syncing) await this.importText(this.modelValue, this._revision)
        smiles = this.modelValue.trim()
      }
      smiles ??= this.modelValue.trim()
      if (this.ready && this.syncError) throw new Error(this.syncError)
      if (smiles) validateChemical(smiles, this.mode)
      return smiles
    },
    async toggleExpanded() {
      try {
        if (document.fullscreenElement === this.$refs.shell) await document.exitFullscreen()
        else await this.$refs.shell.requestFullscreen()
      } catch { this.syncError = 'Full screen is unavailable in this browser. You can continue editing here.' }
    },
    fitDrawing() {
      if (!this.ready || this.importing || this._disposed) return
      const editor = this._ketcher.editor
      const bounds = editor.struct().getCoordBoundingBox()
      const area = editor.render.clientArea.getBoundingClientRect()
      const scale = editor.render.options.microModeScale
      const width = (bounds.max.x - bounds.min.x) * scale
      const height = (bounds.max.y - bounds.min.y) * scale
      if (!width && !height) return
      // Fit using the canvas area between the toolbars. Restore a readable
      // scale when expanding again; Ketcher's default fit only zooms out.
      const zoom = Math.min(1, (area.width - 32) / (width || 1), (area.height - 48) / (height || 1))
      editor.zoom(Math.max(0.1, zoom))
      editor.event.zoomChanged.dispatch()
      editor.centerStruct()
    },
    onFullscreenChange() { this.expanded = document.fullscreenElement === this.$refs.shell },
  },
}
</script>

<style scoped>
.ketcher-editor { border: 1px solid #cbdde6; border-radius: 12px; background: white; overflow: hidden; font-family: var(--font-family); }
.ketcher-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; background: var(--color-primary-light); border-bottom: 1px solid #dbe7ee; }
.ketcher-brand { display: flex; align-items: center; gap: 7px; color: var(--color-primary); font-size: 14px; font-weight: 600; }
.ketcher-brand > span { color: #738a98; font-size: 11px; font-weight: 400; }
.ketcher-expand { display: inline-flex; align-items: center; gap: 6px; border: 1px solid #c6d9e3; border-radius: 6px; background: white; color: var(--color-primary); padding: 5px 8px; font-size: 11px; }
.ketcher-expand:disabled { opacity: .5; }
.ketcher-expand:focus-visible { outline: 3px solid #3ba5be; outline-offset: 2px; }
.ketcher-frame-shell { position: relative; height: 520px; overflow: auto; }
iframe { display: block; border: 0; width: 100%; height: 100%; }
.ketcher-overlay { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; background: #f8fbfdee; color: #527487; font-size: 13px; padding: 24px; text-align: center; }
.ketcher-overlay p { max-width: 320px; margin: 0; }
.ketcher-message { display: flex; gap: 7px; margin: 0; padding: 10px 12px; color: #856039; background: #fff8ed; font-size: 12px; line-height: 1.5; }
.ketcher-footer { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 5px 10px; padding: 9px 12px; color: #6d8592; border-top: 1px solid #e2ebf0; font-size: 11px; }
.ketcher-sync { color: #43827c; }
.ketcher-editor:fullscreen { display: flex; flex-direction: column; border: 0; border-radius: 0; }
.ketcher-editor:fullscreen .ketcher-frame-shell { flex: 1; min-height: 0; height: auto; }
@media (max-width: 575px) { .ketcher-brand > span { display: none; } .ketcher-frame-shell { height: 480px; } }
</style>
