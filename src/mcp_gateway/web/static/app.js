/**
 * MCP Gateway Admin Console - Lightweight Helper Scripts
 */
document.addEventListener('DOMContentLoaded', () => {
  const navButton = document.querySelector('[data-nav-toggle]');
  const navigation = document.getElementById('primary-navigation');

  const closeNavigation = () => {
    const returnFocus = navigation?.contains(document.activeElement);
    navigation?.classList.add('hidden');
    navButton?.setAttribute('aria-expanded', 'false');
    if (returnFocus) navButton?.focus();
  };

  navButton?.classList.remove('hidden');
  navButton?.classList.add('inline-flex');
  navigation?.classList.add('hidden');

  navButton?.addEventListener('click', () => {
    const opening = navigation.classList.contains('hidden');
    navigation.classList.toggle('hidden');
    navButton.setAttribute('aria-expanded', String(opening));
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeNavigation();
  });

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
