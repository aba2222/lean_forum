/**
 * 洛谷 Markdown 编辑器 —— 资源加载器
 *
 * 上游是一整页单应用，脚本依赖严格顺序，而且顶层用了 `const LuoguEditor = ...`，
 * 同一个页面重复插入 <script> 会直接抛 "Identifier has already been declared"。
 * 所以这里统一做一次性顺序加载：谁先调用谁负责注入，后来者只等同一个 Promise。
 *
 * 两套 profile 共用同一份去重表，同一页面同时出现「编辑器」和「已发布内容」时
 * （例如帖子详情页底部还有评论区编辑器）不会重复加载：
 *
 *   editor  —— 编辑器工作区需要的全部资源
 *   content —— 只读渲染已发布内容所需的资源
 *
 * 用法：
 *   编辑器：LMDLoader.register(root)   // 会额外抓 textarea 初值、清本地草稿
 *   内容页：LMDLoader.loadAssets('content')
 */
window.LMDLoader = window.LMDLoader || (function () {
  'use strict';

  var ASSETS = {
    editor: {
      styles: ['katex/katex.min.css', 'prism-tomorrow.min.css', 'styles.scoped.css'],
      scripts: [
        'katex/katex.min.js',
        'prism.js',
        'prism-bundle.js',
        'luogu-parser.js',
        'luogu-linter.js',
        'luogu-math-cheatsheet.js',
        'luogu-templates.js',
        'luogu-typora.js',
        'editor.js'
      ]
    },
    content: {
      styles: ['katex/katex.min.css', 'prism-tomorrow.min.css', 'styles.scoped.css'],
      scripts: [
        'katex/katex.min.js',
        'prism.js',
        'prism-bundle.js',
        'luogu-parser.js'
      ]
    }
  };

  // 已发布内容额外需要一个把「整页应用样式」收窄成「正文样式」的覆盖表
  var CONTENT_ONLY_STYLES = ['luogu-content.css'];

  // 上游的草稿键是全局的，论坛里会让 A 帖的草稿串到 B 帖的表单里
  var STALE_KEYS = [
    'luogu_editor_draft',
    'luogu_editor_doc_name',
    'luogu_editor_theme'
  ];

  var injected = {};        // url -> Promise，同一个文件只注入一次
  var chain = Promise.resolve();

  /** 静态根目录，形如 /static/md_editor/ */
  function staticRoot() {
    var root = document.querySelector('[data-lmd-editor]');
    var fromTemplate = root && root.getAttribute('data-lmd-static-base');
    if (fromTemplate) {
      return fromTemplate.replace(/luogu\/$/, '');
    }
    var tag = document.querySelector('script[src*="luogu-loader.js"]');
    if (tag) {
      return tag.src.replace(/luogu-loader\.js.*$/, '');
    }
    return '/static/md_editor/';
  }

  /** 上游文件在 luogu/ 下，我们自己的适配文件在 staticRoot 下 */
  function upstreamUrl(file) { return staticRoot() + 'luogu/' + file; }
  function ownUrl(file) { return staticRoot() + file; }

  function addStyle(href) {
    if (document.querySelector('link[data-lmd-asset][href="' + href + '"]')) return;
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    link.setAttribute('data-lmd-asset', '');
    document.head.appendChild(link);
  }

  function addScript(src) {
    return new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = src;
      script.setAttribute('data-lmd-asset', '');
      script.onload = function () { resolve(); };
      script.onerror = function () { reject(new Error('加载失败: ' + src)); };
      document.head.appendChild(script);
    });
  }

  /** 排进同一条串行队列，保证脚本执行顺序与数组一致 */
  function enqueue(url) {
    if (injected[url]) return injected[url];
    var promise = chain.then(function () { return addScript(url); });
    chain = promise.catch(function () { /* 单个失败不阻塞后续 */ });
    injected[url] = promise;
    return promise;
  }

  function clearStaleDrafts() {
    for (var i = 0; i < STALE_KEYS.length; i++) {
      try { window.localStorage.removeItem(STALE_KEYS[i]); } catch (e) { /* 隐私模式下忽略 */ }
    }
  }

  function loadAssets(profile) {
    var spec = ASSETS[profile];
    if (!spec) return Promise.reject(new Error('未知的资源集: ' + profile));

    spec.styles.forEach(function (file) { addStyle(upstreamUrl(file)); });
    if (profile === 'content') {
      CONTENT_ONLY_STYLES.forEach(function (file) { addStyle(ownUrl(file)); });
    }

    return spec.scripts.reduce(function (p, file) {
      return p.then(function () { return enqueue(upstreamUrl(file)); });
    }, Promise.resolve());
  }

  function register(root) {
    if (!root) {
      console.error('[lmd] register(): 找不到编辑器容器');
      return;
    }

    var textarea = root.querySelector('#editorTextarea');
    var initial = textarea ? textarea.value : '';

    clearStaleDrafts();

    loadAssets('editor').then(function () {
      if (!window.LMDWidget) {
        console.error('[lmd] luogu-widget.js 未加载，编辑器无法初始化');
        root.classList.add('lmd-widget-broken');
        return;
      }
      window.LMDWidget.init(root, initial);
    }).catch(function (err) {
      console.error('[lmd] 资源加载失败，编辑器降级为普通文本框', err);
      root.classList.add('lmd-widget-broken');
      if (textarea) textarea.classList.add('form-control');
    });
  }

  return { register: register, loadAssets: loadAssets, staticRoot: staticRoot };
})();
