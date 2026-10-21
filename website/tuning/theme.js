try{const t=localStorage.getItem('monofuki-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch{}
addEventListener('DOMContentLoaded',()=>{
  const buttons=[...document.querySelectorAll('[data-theme-choice]')];
  const sync=()=>{const theme=document.documentElement.dataset.theme||(matchMedia('(prefers-color-scheme:light)').matches?'light':'dark');for(const button of buttons)button.setAttribute('aria-pressed',String(button.dataset.themeChoice===theme));};
  for(const button of buttons)button.addEventListener('click',()=>{const theme=button.dataset.themeChoice;document.documentElement.dataset.theme=theme;try{localStorage.setItem('monofuki-theme',theme)}catch{}sync();if(typeof render==='function')render();});
  matchMedia('(prefers-color-scheme:light)').addEventListener('change',sync);sync();
});
