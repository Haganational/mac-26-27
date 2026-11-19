/* Color-changing specs on a masthead photo (img.specs): a random mode each load, a tap for the next one. */
(function () {
  var modes = ['spectrum', 'metro', 'disco', 'glow', 'tide'];
  var pics = document.querySelectorAll('img.specs');
  if (!pics.length) return;
  var st = document.createElement('style');
  st.textContent = "/* color-changing specs (a masthead photo with photo_fx \"glasses\"): the photo is black and white with colored frames,\n   so hue-rotate only moves the frames. nav.js picks a mode per load; a tap cycles to the next. */\nimg.specs { filter: none !important; cursor: pointer; animation: specs-spectrum 7s linear infinite; }\nimg.specs[data-mode=\"metro\"] { animation: specs-metro 6.5s steps(1, end) infinite; }\nimg.specs[data-mode=\"disco\"] { animation: specs-disco 1.2s steps(1, end) infinite; }\nimg.specs[data-mode=\"glow\"] { animation: specs-glow 3.2s ease-in-out infinite; }\nimg.specs[data-mode=\"tide\"] { animation: specs-tide 9s ease-in-out infinite alternate; }\n@keyframes specs-spectrum { from { filter: hue-rotate(0deg); } to { filter: hue-rotate(360deg); } }\n@keyframes specs-metro { /* the frames are orange (about 20deg); each stop lands on a Metro school color */\n  0% { filter: hue-rotate(0deg); } 12.5% { filter: hue-rotate(-20deg); } 25% { filter: hue-rotate(195deg); } 37.5% { filter: hue-rotate(250deg); }\n  50% { filter: hue-rotate(130deg); } 62.5% { filter: hue-rotate(25deg); } 75% { filter: hue-rotate(-35deg); } 87.5% { filter: hue-rotate(180deg); } }\n@keyframes specs-disco { 0% { filter: hue-rotate(0deg) saturate(1.6); } 16% { filter: hue-rotate(120deg) saturate(1.8); } 33% { filter: hue-rotate(240deg) saturate(1.6); }\n  50% { filter: hue-rotate(60deg) saturate(2); } 66% { filter: hue-rotate(300deg) saturate(1.8); } 83% { filter: hue-rotate(180deg) saturate(2); } }\n@keyframes specs-glow { 0%, 100% { filter: hue-rotate(0deg) saturate(1); } 50% { filter: hue-rotate(-160deg) saturate(2.4) brightness(1.08); } }\n@keyframes specs-tide { from { filter: hue-rotate(150deg); } to { filter: hue-rotate(260deg); } }\n@media (prefers-reduced-motion: reduce) { img.specs, img.specs[data-mode] { animation: none; filter: hue-rotate(var(--specs-hue, 0deg)) !important; } }\n";
  document.head.appendChild(st);
  var i = Math.floor(Math.random() * modes.length);
  Array.prototype.forEach.call(pics, function (img) {
    img.dataset.mode = modes[i]; img.style.setProperty('--specs-hue', Math.floor(Math.random() * 360) + 'deg');
    img.title = 'Tap to change the glasses';
    img.addEventListener('click', function (e) {
      e.preventDefault(); e.stopPropagation();
      var n = (modes.indexOf(img.dataset.mode) + 1) % modes.length;
      img.dataset.mode = modes[n]; img.style.setProperty('--specs-hue', Math.floor(Math.random() * 360) + 'deg');
    });
  });
})();
