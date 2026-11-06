/**
 * FoodBridge Vendored Local SVG Icons
 * Eliminates external unpkg.com CDN dependency by inlining hardened SVG symbols directly.
 * Zero network round-trips, zero CSP external script vulnerabilities.
 */
(function () {
  'use strict';

  const ICON_PATHS = {
    'chevron-down': '<path d="m6 9 6 6 6-6"/>',
    'menu': '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
    'x': '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>'
  };

  function renderIcons() {
    const elements = document.querySelectorAll('[data-lucide]');
    elements.forEach(function (el) {
      const name = el.getAttribute('data-lucide');
      const pathContent = ICON_PATHS[name];
      if (!pathContent) return;

      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.setAttribute('fill', 'none');
      svg.setAttribute('stroke', 'currentColor');
      svg.setAttribute('stroke-width', '2');
      svg.setAttribute('stroke-linecap', 'round');
      svg.setAttribute('stroke-linejoin', 'round');

      // Preserve existing CSS classes
      const existingClass = el.getAttribute('class');
      if (existingClass) {
        svg.setAttribute('class', existingClass);
      } else {
        svg.setAttribute('class', 'w-5 h-5');
      }

      svg.innerHTML = pathContent;
      el.parentNode.replaceChild(svg, el);
    });
  }

  // Export compatible global API
  window.lucide = {
    createIcons: renderIcons
  };

  // Run automatically when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderIcons);
  } else {
    renderIcons();
  }
})();

