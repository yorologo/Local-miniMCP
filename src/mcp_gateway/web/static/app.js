/**
 * MCP Gateway Admin Console - Lightweight Helper Scripts
 */
document.addEventListener('DOMContentLoaded', () => {
  // Confirm actions with data-confirm
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      const msg = el.getAttribute('data-confirm') || 'Are you sure?';
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });
});
