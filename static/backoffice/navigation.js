(function () {
  'use strict';
  const search = document.getElementById('menu-search');
  const links = Array.from(document.querySelectorAll('.nav-sidebar .nav-item'));
  links.forEach(function (item) {
    const link = item.querySelector('a');
    if (link.pathname === location.pathname || (link.pathname !== '/admin/' && location.pathname.startsWith(link.pathname))) {
      link.classList.add('active'); link.setAttribute('aria-current', 'page');
    }
  });
  search.addEventListener('input', function () {
    let count = 0;
    links.forEach(function (item) {
      const match = item.textContent.toLowerCase().includes(search.value.trim().toLowerCase());
      item.hidden = !match; if (match) count++;
    });
    document.querySelectorAll('.nav-sidebar .nav-header').forEach(function (header) { header.hidden = Boolean(search.value.trim()); });
    document.getElementById('menu-empty').hidden = count !== 0;
  });
  document.getElementById('menu-search-toggle').addEventListener('click', function () {
    if (window.innerWidth < 992) document.body.classList.add('sidebar-open');
    document.body.classList.remove('sidebar-collapse');
    search.focus();
  });
  const fullscreen = document.getElementById('fullscreen-toggle');
  if (!document.fullscreenEnabled) fullscreen.hidden = true;
  fullscreen.addEventListener('click', async function () {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (error) { fullscreen.title = 'เบราว์เซอร์ไม่อนุญาตให้เปิดเต็มหน้าจอ'; }
  });
  document.addEventListener('fullscreenchange', function () {
    fullscreen.setAttribute('aria-label', document.fullscreenElement ? 'ออกจากเต็มหน้าจอ' : 'เปิดเต็มหน้าจอ');
  });
}());
