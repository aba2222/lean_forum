/* 昵称悬停名片。
 *
 * 页面上凡是 {% user_link %} 渲染出来的昵称，都带一个 data-user-card，
 * 值是名片接口的 URL。这里用事件委托监听整页：
 * 鼠标移到（或键盘 focus 到）这类链接上才去取一次数据，取到之后缓存住。
 *
 * 数据全部用 textContent 写进 DOM，不用 innerHTML —— 昵称和简介都是
 * 用户可控的内容，拼 HTML 等于给自己开一个 XSS 口子。
 */
(function () {
  'use strict';

  var SHOW_DELAY = 140;
  var HIDE_DELAY = 200;
  var CARD_WIDTH = 260;
  var GAP = 8;

  var cache = Object.create(null);
  var card = null;
  var activeLink = null;
  var showTimer = null;
  var hideTimer = null;
  var requestToken = 0;

  function ensureCard() {
    if (card) {
      return card;
    }
    card = document.createElement('div');
    card.className = 'user-card';
    card.setAttribute('role', 'tooltip');
    card.hidden = true;
    // 鼠标能移进名片里（比如以后加关注按钮），移出去就收起来
    card.addEventListener('mouseenter', function () {
      window.clearTimeout(hideTimer);
    });
    card.addEventListener('mouseleave', scheduleHide);
    document.body.appendChild(card);
    return card;
  }

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function avatarNode(data) {
    if (data.avatar_url) {
      var image = element('img', 'user-card-avatar');
      image.src = data.avatar_url;
      image.alt = '';
      return image;
    }
    var initial = element('span', 'user-card-avatar user-card-initial', data.initial);
    initial.style.backgroundColor = data.color;
    return initial;
  }

  function render(data) {
    var node = ensureCard();
    node.textContent = '';

    var head = element('div', 'user-card-head');
    head.appendChild(avatarNode(data));

    var meta = element('div');
    meta.appendChild(element('div', 'user-card-name', data.username));
    meta.appendChild(element('div', 'user-card-joined', data.joined + ' 加入'));
    head.appendChild(meta);
    node.appendChild(head);

    if (data.bio) {
      node.appendChild(element('p', 'user-card-bio', data.bio));
    }

    var stats = element('div', 'user-card-stats');
    stats.appendChild(element('span', null, data.posts + ' 帖子'));
    stats.appendChild(element('span', null, data.comments + ' 评论'));
    node.appendChild(stats);

    return node;
  }

  function position(link) {
    var node = ensureCard();
    var rect = link.getBoundingClientRect();
    var height = node.offsetHeight;

    var left = rect.left;
    if (left + CARD_WIDTH > window.innerWidth - GAP) {
      left = Math.max(GAP, window.innerWidth - CARD_WIDTH - GAP);
    }

    // 下方放不下就翻到上面
    var top = rect.bottom + GAP;
    if (top + height > window.innerHeight - GAP) {
      top = Math.max(GAP, rect.top - height - GAP);
    }

    node.style.left = left + 'px';
    node.style.top = top + 'px';
  }

  function scheduleHide() {
    window.clearTimeout(showTimer);
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(hide, HIDE_DELAY);
  }

  function hide() {
    window.clearTimeout(showTimer);
    window.clearTimeout(hideTimer);
    activeLink = null;
    if (card) {
      card.hidden = true;
    }
  }

  function show(link, data) {
    render(data);
    card.hidden = false;
    position(link);
  }

  function onEnter(link) {
    window.clearTimeout(hideTimer);
    window.clearTimeout(showTimer);
    activeLink = link;

    showTimer = window.setTimeout(function () {
      var url = link.getAttribute('data-user-card');
      if (!url) {
        return;
      }

      if (cache[url]) {
        show(link, cache[url]);
        return;
      }

      var token = ++requestToken;
      fetch(url, {
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error('HTTP ' + response.status);
          }
          return response.json();
        })
        .then(function (data) {
          cache[url] = data;
          // 取回数据的过程中鼠标可能已经移开了
          if (token === requestToken && activeLink === link) {
            show(link, data);
          }
        })
        .catch(function () {
          // 名片是锦上添花的东西，失败了就当没这个功能
        });
    }, SHOW_DELAY);
  }

  function linkFrom(event) {
    var target = event.target;
    if (!target || !target.closest) {
      return null;
    }
    return target.closest('[data-user-card]');
  }

  document.addEventListener('mouseover', function (event) {
    var link = linkFrom(event);
    if (link && link !== activeLink) {
      onEnter(link);
    } else if (!link && activeLink) {
      scheduleHide();
    }
  });

  // 键盘用户：tab 到昵称上也应该能看到名片
  document.addEventListener('focusin', function (event) {
    var link = linkFrom(event);
    if (link) {
      onEnter(link);
    }
  });

  document.addEventListener('focusout', function () {
    scheduleHide();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      hide();
    }
  });

  // 页面滚动后名片会飘在原来的位置上，直接收起来最省事
  window.addEventListener('scroll', hide, { passive: true });
  window.addEventListener('resize', hide);
})();
