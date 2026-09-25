/**
 * 洛谷 Markdown —— 已发布内容的渲染器
 *
 * 目标：帖子里读到的排版和编辑器右侧预览**完全一致**。
 * 做法是复用同一个解析器（上游 luogu-parser.js），而不是在服务端再写一套：
 * 两份解析器迟早会漂移，一份不会。
 *
 * 服务端仍然会把 content 渲染成 content_html（markdown-it + bleach），
 * 那是给「脚本没跑起来」时的兜底；脚本就绪后会被这里的渲染结果替换掉。
 *
 * 容器约定（见 forum/templates/forum/_markdown.html）：
 *
 *   <div class="lmd-root lmd-content" data-luogu-markdown="<原始 Markdown>">
 *     <div class="preview-content"><服务端兜底 HTML></div>
 *   </div>
 *
 * 上游解析器会输出三个全局函数调用（复制代码、任务清单勾选、B 站播放器），
 * 编辑器里由 editor.js 提供；只读页面不该为了这三个小函数去加载 139KB 的
 * editor.js，所以这里自己实现，并且把任务清单设成只读。
 */
window.LuoguRender = window.LuoguRender || (function () {
  'use strict';

  var started = false;

  // ---- 上游解析器输出需要的三个全局函数 ----

  function installGlobals() {
    window.copyCodeBlock = function (btn) {
      var wrapper = btn.closest('.luogu-code-block-wrapper');
      if (!wrapper) return;

      var lines = [].map.call(wrapper.querySelectorAll('.code-line-text'), function (el) {
        return el.innerText;
      });
      var codeEl = wrapper.querySelector('pre code');
      var text = lines.length ? lines.join('\n') : (codeEl ? codeEl.innerText : '');

      var done = function () {
        var span = btn.querySelector('.copy-text') || btn;
        var old = span.innerText;
        span.innerText = '✓ 已复制';
        btn.style.borderColor = '#2ecc71';
        btn.style.color = '#2ecc71';
        setTimeout(function () {
          span.innerText = old;
          btn.style.borderColor = '';
          btn.style.color = '';
        }, 1800);
      };

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {
          window.alert('复制失败，请手动选择复制');
        });
      } else {
        window.alert('当前浏览器不支持一键复制，请手动选择复制。');
      }
    };

    // 阅读视图里任务清单是只读的：勾选不会写回 Markdown，放开只会让人误以为能改
    window.toggleTaskCheckbox = function (checkbox) {
      checkbox.checked = !checkbox.checked;
    };

    // 与 editor.js 里的实现保持一致：点击后才向 bilibili 发请求
    window.loadBilibiliPlayer = function (btn) {
      var src = btn.getAttribute('data-src');
      if (!src) return;

      var iframe = document.createElement('iframe');
      iframe.setAttribute('src', src);
      iframe.setAttribute('scrolling', 'no');
      iframe.setAttribute('frameborder', 'no');
      iframe.setAttribute('framespacing', '0');
      iframe.setAttribute('allowfullscreen', 'true');
      iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
      iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-popups allow-presentation');
      iframe.setAttribute('data-src', src);
      btn.replaceWith(iframe);
    };
  }

  // ---- 渲染 ----

  function containers() {
    return document.querySelectorAll('[data-luogu-markdown]');
  }

  function target(container) {
    return container.querySelector('.preview-content') || container;
  }

  /** 渲染成功后摘掉兜底标记，兜底样式随即失效（见 luogu-content.css） */
  function dropFallback(container) {
    var fallback = container.querySelector('.lmd-fallback');
    if (fallback) fallback.classList.remove('lmd-fallback');
  }

  function makeReadOnly(scope) {
    var boxes = scope.querySelectorAll('.luogu-task-checkbox');
    for (var i = 0; i < boxes.length; i++) {
      boxes[i].disabled = true;
    }
  }

  function renderAll() {
    var parser = new window.LuoguParser();
    var list = containers();

    for (var i = 0; i < list.length; i++) {
      var container = list[i];
      var source = container.getAttribute('data-luogu-markdown') || '';

      // 空内容保留服务端兜底结果，别把容器清成空白
      if (!source.trim()) {
        container.classList.add('lmd-rendered');
        continue;
      }

      try {
        target(container).innerHTML = parser.render(source);
        dropFallback(container);
        container.classList.add('lmd-rendered');
      } catch (err) {
        // 单个容器失败不影响其它容器，也不清掉服务端兜底内容
        console.error('[lmd] 内容渲染失败，保留服务端版本', err);
      }
    }

    makeReadOnly(document);
  }

  function start() {
    if (started) return;
    started = true;

    if (!containers().length) return;

    if (!window.LMDLoader) {
      console.error('[lmd] 缺少 luogu-loader.js，已发布内容保持服务端渲染');
      return;
    }

    installGlobals();

    window.LMDLoader.loadAssets('content').then(function () {
      if (!window.LuoguParser) {
        console.error('[lmd] luogu-parser.js 未加载，已发布内容保持服务端渲染');
        return;
      }
      renderAll();
    }).catch(function (err) {
      console.error('[lmd] 资源加载失败，已发布内容保持服务端渲染', err);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

  return { start: start, render: renderAll };
})();
