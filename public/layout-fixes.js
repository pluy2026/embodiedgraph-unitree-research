/* Interaction handlers live in review.js so graph redraws cannot reset the detail panel. */
if (!document.querySelector('link[href^="intro.css"]')) {
  const introStyles = document.createElement('link');
  introStyles.rel = 'stylesheet';
  introStyles.href = 'intro.css?v=scene-transition-1';
  document.head.append(introStyles);
}
if (!document.querySelector('link[href^="page-overrides.css"]')) {
  const pageStyles = document.createElement('link');
  pageStyles.rel = 'stylesheet';
  pageStyles.href = 'page-overrides.css?v=review-assets-1';
  document.head.append(pageStyles);
}

/* The overview opens as a two-step editorial transition.  It is mounted here
   because review.js re-renders the whole shell whenever the user changes tabs. */
(() => {
  const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  function activateIntro() {
    const stage = document.querySelector('.overview-film');
    if (!stage || stage.dataset.introMounted) return;

    stage.dataset.introMounted = 'true';
    stage.className = 'overview-intro';
    const metricTargets = [...document.querySelectorAll('.overview-metrics [data-count]')]
      .map((node) => `${node.dataset.count || '0'}${node.dataset.suffix || ''}`);
    const [firmCount = '0', relationCount = '0', confirmedRate = '0%', reviewCount = '0'] = metricTargets;

    stage.innerHTML = `
      <button class="intro-scene" type="button" aria-label="进入研究结论页">
        <span class="intro-scene-hint">点击进入研究结论</span>
      </button>
      <div class="intro-robot-pass" aria-hidden="true"></div>
      <div class="intro-title-pass" aria-hidden="true">
        <span class="film-kicker">EMBODIEDGRAPH / OFFLINE RESEARCH</span>
        <strong><i>TRACE THE</i>EMBODIED WEB</strong>
        <em>宇树科技产业关系研究<br>Evidence-led relationship snapshot</em>
      </div>
      <button class="intro-result" type="button" aria-label="进入研究方法页">
        <span class="intro-result-kicker">RESEARCH POSITION</span>
        <div class="intro-result-copy">
          <div>
            <h1>每一条关系，<br>都必须回到证据。</h1>
            <p>系统区分已确认、较高可能与待验证；研究结论不等同于商业重要性，也不由视觉效果替代判断边界。</p>
          </div>
          <div class="intro-result-rule"><span>01</span><b>可追溯</b><p>关系卡直接连接至原始来源、定位与不确定性说明。</p></div>
        </div>
        <div class="intro-result-stats" aria-label="研究原则">
          <span><b>${firmCount}</b><small>关联实体<br>图谱中可见节点</small></span>
          <span><b>${relationCount}</b><small>关系记录<br>含方向与时间边界</small></span>
          <span><b>${confirmedRate}</b><small>已确认<br>可直接复核</small></span>
          <span><b>${reviewCount}</b><small>待复核<br>不作为事实呈现</small></span>
        </div>
        <span class="intro-next-hint">点击查看研究结论 ↓</span>
      </button>`;

    const scene = stage.querySelector('.intro-scene');
    const result = stage.querySelector('.intro-result');
    const brief = document.querySelector('.overview-brief');
    const conclusions = brief?.querySelector('.brief-conclusions');
    const reviewPage = brief?.querySelector('.brief-review');

    if (brief && conclusions && reviewPage) {
      brief.classList.add('overview-pages');
      brief.hidden = true;
      reviewPage.hidden = true;
      conclusions.insertAdjacentHTML('beforeend', '<span class="overview-page-next">点击查看优先复核 ↓</span>');
    }

    const openResult = () => {
      if (stage.classList.contains('intro-open')) return;
      stage.classList.add('intro-open');
      if (reducedMotion()) stage.classList.add('intro-finished');
    };
    const goToThird = () => {
      if (!brief || !conclusions || !reviewPage || stage.classList.contains('intro-closing')) return;
      stage.classList.add('intro-closing');
      window.setTimeout(() => {
        stage.hidden = true;
        brief.hidden = false;
        conclusions.hidden = false;
        reviewPage.hidden = true;
        conclusions.classList.add('page-active', 'is-visible');
        window.scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' });
      }, reducedMotion() ? 0 : 360);
    };
    const showReview = () => {
      if (!brief || !conclusions || !reviewPage || reviewPage.hidden === false) return;
      conclusions.classList.remove('page-active');
      conclusions.hidden = true;
      reviewPage.hidden = false;
      reviewPage.classList.add('page-active', 'is-visible');
      window.scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' });
    };

    scene.addEventListener('click', openResult);
    result.addEventListener('click', goToThird);
    conclusions?.addEventListener('click', showReview);
    [scene, result].forEach((node) => node.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        node === scene ? openResult() : goToThird();
      }
    }));
  }

  const observer = new MutationObserver(activateIntro);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener('DOMContentLoaded', activateIntro);
  activateIntro();
})();
