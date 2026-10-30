/**
 * Detects usable WebGL (2 preferred, 1 as fallback) so the 3D exhibit can
 * degrade to a static sculpture instead of a blank canvas.
 */
export function hasWebGLSupport(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    if (window.WebGL2RenderingContext && canvas.getContext('webgl2')) return true
    if (window.WebGLRenderingContext && canvas.getContext('webgl')) return true
    return false
  } catch {
    return false
  }
}
