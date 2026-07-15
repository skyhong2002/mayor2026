(function () {
  const body = document.body;
  const base = body.dataset.base || "";
  const FEED_PAGE_SIZE = 30;
  const INTENT_LABELS = { self_initiated: "主動發文", responsive: "回應他方觀點" };

  const PLATFORM_LABELS = {
    website: "官網",
    facebook: "Facebook",
    instagram: "Instagram",
    threads: "Threads",
    youtube: "YouTube",
    x: "X",
    line_oa: "LINE 官方帳號",
    line_openchat: "LINE 社群",
    tiktok: "TikTok",
    podcast: "Podcast",
  };

  // Platform icon SVGs from the Harmonica-in-Taiwan project.
  const PLATFORM_ICONS = {
    facebook: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M14 13.5H16.5L17.5 9.5H14V7.5C14 6.47062 14 5.5 16 5.5H17.5V2.1401C17.1743 2.09685 15.943 2 14.6429 2C11.9284 2 10 3.65686 10 6.69971V9.5H7V13.5H10V22H14V13.5Z"/></svg>',
    instagram: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12.001 9C10.3436 9 9.00098 10.3431 9.00098 12C9.00098 13.6573 10.3441 15 12.001 15C13.6583 15 15.001 13.6569 15.001 12C15.001 10.3427 13.6579 9 12.001 9ZM12.001 7C14.7614 7 17.001 9.2371 17.001 12C17.001 14.7605 14.7639 17 12.001 17C9.24051 17 7.00098 14.7629 7.00098 12C7.00098 9.23953 9.23808 7 12.001 7ZM18.501 6.74915C18.501 7.43926 17.9402 7.99917 17.251 7.99917C16.5609 7.99917 16.001 7.4384 16.001 6.74915C16.001 6.0599 16.5617 5.5 17.251 5.5C17.9393 5.49913 18.501 6.0599 18.501 6.74915ZM12.001 4C9.5265 4 9.12318 4.00655 7.97227 4.0578C7.18815 4.09461 6.66253 4.20007 6.17416 4.38967C5.74016 4.55799 5.42709 4.75898 5.09352 5.09255C4.75867 5.4274 4.55804 5.73963 4.3904 6.17383C4.20036 6.66332 4.09493 7.18811 4.05878 7.97115C4.00703 9.0752 4.00098 9.46105 4.00098 12C4.00098 14.4745 4.00753 14.8778 4.05877 16.0286C4.0956 16.8124 4.2012 17.3388 4.39034 17.826C4.5591 18.2606 4.7605 18.5744 5.09246 18.9064C5.42863 19.2421 5.74179 19.4434 6.17187 19.6094C6.66619 19.8005 7.19148 19.9061 7.97212 19.9422C9.07618 19.9939 9.46203 20 12.001 20C14.4755 20 14.8788 19.9934 16.0296 19.9422C16.8117 19.9055 17.3385 19.7996 17.827 19.6106C18.2604 19.4423 18.5752 19.2402 18.9074 18.9085C19.2436 18.5718 19.4445 18.2594 19.6107 17.8283C19.8013 17.3358 19.9071 16.8098 19.9432 16.0289C19.9949 14.9248 20.001 14.5389 20.001 12C20.001 9.52552 19.9944 9.12221 19.9432 7.97137C19.9064 7.18906 19.8005 6.66149 19.6113 6.17318C19.4434 5.74038 19.2417 5.42635 18.9084 5.09255C18.573 4.75715 18.2616 4.55693 17.8271 4.38942C17.338 4.19954 16.8124 4.09396 16.0298 4.05781C14.9258 4.00605 14.5399 4 12.001 4ZM12.001 2C14.7176 2 15.0568 2.01 16.1235 2.06C17.1876 2.10917 17.9135 2.2775 18.551 2.525C19.2101 2.77917 19.7668 3.1225 20.3226 3.67833C20.8776 4.23417 21.221 4.7925 21.476 5.45C21.7226 6.08667 21.891 6.81333 21.941 7.8775C21.9885 8.94417 22.001 9.28333 22.001 12C22.001 14.7167 21.991 15.0558 21.941 16.1225C21.8918 17.1867 21.7226 17.9125 21.476 18.55C21.2218 19.2092 20.8776 19.7658 20.3226 20.3217C19.7668 20.8767 19.2076 21.22 18.551 21.475C17.9135 21.7217 17.1876 21.89 16.1235 21.94C15.0568 21.9875 14.7176 22 12.001 22C9.28431 22 8.94514 21.99 7.87848 21.94C6.81431 21.8908 6.08931 21.7217 5.45098 21.475C4.79264 21.2208 4.23514 20.8767 3.67931 20.3217C3.12348 19.7658 2.78098 19.2067 2.52598 18.55C2.27848 17.9125 2.11098 17.1867 2.06098 16.1225C2.01348 15.0558 2.00098 14.7167 2.00098 12C2.00098 9.28333 2.01098 8.94417 2.06098 7.8775C2.11014 6.8125 2.27848 6.0875 2.52598 5.45C2.78014 4.79167 3.12348 4.23417 3.67931 3.67833C4.23514 3.1225 4.79348 2.78 5.45098 2.525C6.08848 2.2775 6.81348 2.11 7.87848 2.06C8.94514 2.0125 9.28431 2 12.001 2Z"/></svg>',
    threads: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12.1835 1.41016L12.1822 1.41016C9.09012 1.43158 6.70036 2.47326 5.09369 4.51569C3.66581 6.33087 2.93472 8.86436 2.91016 12.0068V12.0082C2.93472 15.1508 3.66586 17.6696 5.09369 19.4847C6.70043 21.5271 9.10257 22.5688 12.1946 22.5902H12.1958C14.944 22.5711 16.8929 21.8504 18.4985 20.2463C20.6034 18.1434 20.5408 15.5048 19.8456 13.8832C19.3163 12.6493 18.2709 11.6618 16.8701 11.0477C16.6891 8.06345 15.0097 6.32178 12.2496 6.30415C10.6191 6.29409 9.14792 7.02378 8.24685 8.39104L9.90238 9.5267C10.4353 8.71818 11.2789 8.32815 12.2371 8.33701C13.6244 8.34586 14.5362 9.11128 14.7921 10.4541C14.02 10.3333 13.1902 10.2982 12.3076 10.3488C9.66843 10.5008 7.9399 12.061 8.05516 14.2244C8.17571 16.4862 10.367 17.7186 12.4476 17.605C14.9399 17.4684 16.4209 15.6292 16.7722 13.2836C17.3493 13.6575 17.7751 14.1344 18.0163 14.6969C18.4559 15.7222 18.4838 17.4132 17.1006 18.7952C15.8838 20.0108 14.4211 20.5407 12.1891 20.5572C9.71428 20.5388 7.85698 19.746 6.65154 18.2136C5.51973 16.7748 4.92843 14.6882 4.90627 12.0002C4.92843 9.31211 5.51973 7.22549 6.65154 5.78673C7.85698 4.25433 9.71424 3.46156 12.189 3.44303C14.6819 3.4617 16.5728 4.25837 17.8254 5.79937C18.5162 6.64934 18.949 7.66539 19.2379 8.71407L21.1776 8.19656C20.8148 6.85917 20.2414 5.58371 19.363 4.50305C17.7098 2.46918 15.2816 1.43166 12.1835 1.41016ZM12.4204 12.3782C13.3044 12.3272 14.1239 12.3834 14.8521 12.5345C14.7114 14.1116 14.0589 15.4806 12.3401 15.575C11.2282 15.6376 10.1031 15.1413 10.0484 14.114C10.0077 13.3503 10.5726 12.4847 12.4204 12.3782Z"/></svg>',
    youtube: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12.2439 4C12.778 4.00294 14.1143 4.01586 15.5341 4.07273L16.0375 4.09468C17.467 4.16236 18.8953 4.27798 19.6037 4.4755C20.5486 4.74095 21.2913 5.5155 21.5423 6.49732C21.942 8.05641 21.992 11.0994 21.9982 11.8358L21.9991 11.9884L21.9991 11.9991C21.9991 11.9991 21.9991 12.0028 21.9991 12.0099L21.9982 12.1625C21.992 12.8989 21.942 15.9419 21.5423 17.501C21.2878 18.4864 20.5451 19.261 19.6037 19.5228C18.8953 19.7203 17.467 19.8359 16.0375 19.9036L15.5341 19.9255C14.1143 19.9824 12.778 19.9953 12.2439 19.9983L12.0095 19.9991L11.9991 19.9991C11.9991 19.9991 11.9956 19.9991 11.9887 19.9991L11.7545 19.9983C10.6241 19.9921 5.89772 19.941 4.39451 19.5228C3.4496 19.2573 2.70692 18.4828 2.45587 17.501C2.0562 15.9419 2.00624 12.8989 2 12.1625V11.8358C2.00624 11.0994 2.0562 8.05641 2.45587 6.49732C2.7104 5.51186 3.45308 4.73732 4.39451 4.4755C5.89772 4.05723 10.6241 4.00622 11.7545 4H12.2439ZM9.99911 8.49914V15.4991L15.9991 11.9991L9.99911 8.49914Z"/></svg>',
    x: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M10.4883 14.651L15.25 21H22.25L14.3917 10.5223L20.9308 3H18.2808L13.1643 8.88578L8.75 3H1.75L9.26086 13.0145L2.31915 21H4.96917L10.4883 14.651ZM16.25 19L5.75 5H7.75L18.25 19H16.25Z"/></svg>',
    generic: '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle class="platform-icon-stroke" cx="12" cy="12" r="7"/><path class="platform-icon-stroke" d="M5 12h14M12 5c2 2 3 4.3 3 7s-1 5-3 7M12 5c-2 2-3 4.3-3 7s1 5 3 7"/></svg>',
  };

  function platformIconLink(account) {
    const key = PLATFORM_ICONS[account.platform] ? account.platform : "generic";
    const label = PLATFORM_LABELS[account.platform] || account.platform;
    const a = el("a", `directory-link-icon platform-badge platform-badge-${account.platform}`);
    a.href = account.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.title = label;
    a.setAttribute("aria-label", label);
    a.innerHTML = PLATFORM_ICONS[key];
    return a;
  }

  function fetchJson(path) {
    return fetch(base + path).then((res) => {
      if (!res.ok) throw new Error(`fetch failed: ${path} (${res.status})`);
      return res.json();
    });
  }

  function formatDate(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString("zh-TW", { dateStyle: "medium", timeStyle: "short" });
  }

  // Relative time (X秒前/X分鐘前/X小時前/X天前) for post and "最後更新"
  // timestamps — used everywhere content freshness matters, so the reader
  // feels how recent something is instead of parsing an absolute date.
  function formatRelative(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    const diffSec = Math.round((Date.now() - date.getTime()) / 1000);
    if (diffSec < 5) return "剛剛";
    if (diffSec < 60) return `${diffSec} 秒前`;
    const diffMin = Math.round(diffSec / 60);
    if (diffMin < 60) return `${diffMin} 分鐘前`;
    const diffHour = Math.round(diffMin / 60);
    if (diffHour < 24) return `${diffHour} 小時前`;
    const diffDay = Math.round(diffHour / 24);
    return `${diffDay} 天前`;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function avatarNode(candidate, small) {
    const avatar = el("span", small ? "source-avatar source-avatar-small" : "source-avatar");
    if (candidate && candidate.avatarUrl) {
      const img = document.createElement("img");
      img.src = base + candidate.avatarUrl;
      img.alt = candidate.name || "";
      img.loading = "lazy";
      avatar.appendChild(img);
    } else {
      avatar.textContent = ((candidate && candidate.name) || "?").slice(0, 2);
    }
    return avatar;
  }

  function feedCard(post, candidate) {
    const card = el("article", "home-feed-card");

    const account =
      candidate && candidate.accounts
        ? candidate.accounts.find((a) => a.id === post.sourceId)
        : null;

    const source = el("div", "home-feed-source");
    const sourceMain = el("div", "home-feed-source-main");
    // The card identity is the platform account itself (its own page/channel
    // name and avatar), falling back to the candidate only when the account
    // profile hasn't been fetched yet.
    const identity = {
      name: (account && account.displayName) || (candidate && candidate.name) || post.candidateId,
      avatarUrl: (account && account.avatarUrl) || (candidate && candidate.avatarUrl) || null,
    };
    sourceMain.appendChild(avatarNode(identity, true));
    const nameWrap = el("div");
    nameWrap.appendChild(el("strong", "", identity.name));
    const accountLabel = account
      ? `${account.handle || account.url}`
      : PLATFORM_LABELS[post.platform] || post.platform;
    if (account && account.url) {
      const handleLink = el("a", "data-date", accountLabel);
      handleLink.href = account.url;
      handleLink.target = "_blank";
      handleLink.rel = "noopener";
      handleLink.style.display = "block";
      handleLink.style.textDecoration = "none";
      nameWrap.appendChild(handleLink);
    } else {
      nameWrap.appendChild(el("span", "data-date", accountLabel));
    }
    sourceMain.appendChild(nameWrap);
    source.appendChild(sourceMain);

    const badgeKey = PLATFORM_ICONS[post.platform] ? post.platform : "generic";
    const badgeLabel = PLATFORM_LABELS[post.platform] || post.platform;
    const badge = el("a", `platform-badge platform-badge-${post.platform}`);
    badge.href = (account && account.url) || post.url;
    badge.target = "_blank";
    badge.rel = "noopener";
    badge.title = badgeLabel;
    badge.setAttribute("aria-label", badgeLabel);
    badge.innerHTML = PLATFORM_ICONS[badgeKey];
    source.appendChild(badge);

    card.appendChild(source);

    const hasImage = Boolean(post.imageUrl);
    const bodyEl = el(
      "div",
      "home-feed-body home-feed-body-no-title" + (hasImage ? "" : " home-feed-body-no-image")
    );
    if (hasImage) {
      const thumb = el("span", "home-feed-thumb");
      if (post.imageAspect) thumb.style.setProperty("--feed-image-aspect", String(post.imageAspect));
      const img = document.createElement("img");
      img.src = base + post.imageUrl;
      img.alt = "";
      img.loading = "lazy";
      thumb.appendChild(img);
      bodyEl.appendChild(thumb);
    }
    const excerpt = el("p", "feed-latest-excerpt", post.text || "");
    excerpt.style.margin = "0";
    bodyEl.appendChild(excerpt);
    card.appendChild(bodyEl);

    if (post.topics && post.topics.length) {
      const meta = el("div", "entry-meta");
      post.topics.forEach((topic) => {
        const url = topicPageUrl(topic);
        if (url) {
          const pill = el("a", "pill", topic);
          pill.href = url;
          pill.style.textDecoration = "none";
          meta.appendChild(pill);
        } else {
          meta.appendChild(el("span", "pill", topic));
        }
      });
      card.appendChild(meta);
    }

    const contextMeta = el("div", "entry-meta context-meta");
    const intent = post.postingIntent || { type: "self_initiated", confidence: 0, reason: "AI 分類處理中" };
    const confidence = Math.round((intent.confidence || 0) * 100);
    const intentPill = el("span", `pill intent-pill intent-${intent.type}`, `${INTENT_LABELS[intent.type] || intent.type} ${confidence}%`);
    intentPill.title = `AI 判斷信心 ${confidence}%${intent.reason ? `；${intent.reason}` : ""}`;
    contextMeta.appendChild(intentPill);
    card.appendChild(contextMeta);

    const footer = el("div", "home-feed-footer");
    footer.appendChild(el("p", "entry-meta data-date", formatRelative(post.postedAt)));
    const open = el("a", "feed-open-link", "打開原始貼文 ↗");
    open.href = post.url;
    open.target = "_blank";
    open.rel = "noopener";
    footer.appendChild(open);
    card.appendChild(footer);

    return card;
  }

  function riverColumnCount(river) {
    const width = river.clientWidth || document.documentElement.clientWidth;
    if (width >= 901) return 3;
    if (width >= 620) return 2;
    return 1;
  }

  // Round-robin card distribution into columns, with a "load more" button —
  // the same reading order Harmonica uses for its feed river.
  function createRiver(container, posts, candidatesById) {
    let shown = 0;
    let columns = [];

    const river = el("div", "feed-river");
    container.appendChild(river);

    const moreWrap = el("div", "feed-load-more-wrap");
    const moreButton = el("button", "feed-load-more-button", "載入更多");
    const status = el("p", "feed-load-more-status");
    moreWrap.appendChild(moreButton);
    moreWrap.appendChild(status);
    container.appendChild(moreWrap);

    function rebuildColumns() {
      const count = riverColumnCount(river);
      river.innerHTML = "";
      columns = Array.from({ length: count }, () => {
        const column = el("div", "feed-river-column");
        river.appendChild(column);
        return column;
      });
    }

    function renderUpTo(target) {
      rebuildColumns();
      shown = Math.min(target, posts.length);
      for (let i = 0; i < shown; i += 1) {
        const post = posts[i];
        columns[i % columns.length].appendChild(feedCard(post, candidatesById[post.candidateId]));
      }
      status.textContent = `顯示 ${shown} / ${posts.length} 則`;
      moreWrap.style.display = shown >= posts.length ? "none" : "";
      if (!posts.length) {
        river.appendChild(el("p", "empty-state", "尚無收錄貼文。"));
        status.textContent = "";
      }
    }

    moreButton.addEventListener("click", () => renderUpTo(shown + FEED_PAGE_SIZE));
    let resizeTimer = null;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (riverColumnCount(river) !== columns.length) renderUpTo(shown);
      }, 160);
    });

    renderUpTo(FEED_PAGE_SIZE);
  }

  function renderIndex() {
    Promise.all([fetchJson("api/cities.json"), fetchJson("api/sources.json"), fetchJson("api/latest.json")])
      .then(([citiesPayload, candidatesPayload, latestPayload]) => {
        const candidates = candidatesPayload.sources;
        const candidatesById = Object.fromEntries(candidates.map((c) => [c.id, c]));

        const statRow = document.getElementById("stat-row");
        const totalPosts = candidates.reduce((sum, c) => sum + (c.postCount || 0), 0);
        [
          [String(candidates.length), "監看候選人"],
          ["6", "直轄市"],
          [String(totalPosts), "已收錄貼文"],
        ].forEach(([value, label]) => {
          const cell = el("div", "stat-card");
          cell.appendChild(el("strong", "", value));
          cell.appendChild(el("span", "", label));
          statRow.appendChild(cell);
        });

        const latestAt = candidates
          .map((c) => c.latestPostAt)
          .filter(Boolean)
          .sort()
          .pop();
        if (latestAt) document.getElementById("data-date").textContent = `最後更新 ${formatRelative(latestAt)}`;

        const grid = document.getElementById("city-grid");

        function renderGrid() {
        grid.innerHTML = "";
        const sortWrap = el("div");
        sortWrap.style.gridColumn = "1 / -1";
        sortWrap.appendChild(sortControl(renderGrid));
        grid.appendChild(sortWrap);
        citiesPayload.cities.forEach((city) => {
          const card = el("article", "home-feed-card city-card");
          card.appendChild(el("h3", "city-card-title", city.label));

          if (!city.candidateIds.length) {
            card.appendChild(el("p", "empty-state", "尚無候選人資料"));
          } else {
            const list = el("div", "candidate-city-list");
            sortCandidates(city.candidateIds.map((id) => candidatesById[id]).filter(Boolean)).forEach((candidate) => {
              const candidateId = candidate.id;
              const link = el("a");
              link.href = `source/${candidate.id}/`;
              const identity = el("span", "candidate-city-identity");
              identity.appendChild(avatarNode(candidate, true));
              identity.appendChild(el("strong", "", candidate.name));
              link.appendChild(identity);
              link.appendChild(el("span", "data-date", `${candidate.party || "未標註"} · ${candidate.postCount} 則`));
              list.appendChild(link);
            });
            card.appendChild(list);
          }
          grid.appendChild(card);
        });
        }

        renderGrid();

        const feed = document.getElementById("latest-feed");
        feed.innerHTML = "";
        createRiver(feed, latestPayload.posts, candidatesById);
      })
      .catch((err) => {
        document.getElementById("city-grid").textContent = `資料載入失敗：${err.message}`;
      });
  }

  function renderTopicChart(canvas, topicProportions) {
    const labels = Object.keys(topicProportions || {});
    if (!labels.length || typeof Chart === "undefined") {
      canvas.parentElement.textContent = "尚無足夠貼文計算議題比例。";
      return;
    }
    const values = labels.map((label) => topicProportions[label]);
    new Chart(canvas, {
      type: "pie",
      data: {
        labels,
        datasets: [
          {
            data: values,
            // Same topic->color mapping as the spectrum page.
            backgroundColor: labels.map((label) => TOPIC_COLORS[label] || "#9aa19d"),
          },
        ],
      },
      options: { plugins: { legend: { position: "bottom" } } },
    });
  }

  // Chart + per-topic breakdown + filterable timeline, shared by the merged
  // candidate page (/source/<id>/).
  function renderCandidateAnalytics({ candidateId, sourceEntry, posts, spectrumPayload, topicDetails }) {
    const spectrumEntry = spectrumPayload.candidates.find((c) => c.candidateId === candidateId);
    renderTopicChart(document.getElementById("topic-chart"), spectrumEntry ? spectrumEntry.topicProportions : {});

    // Per-topic breakdown: proportion bar + the keyword sub-items this
    // candidate actually hits within each topic, linking to the
    // cross-candidate topic page.
    const breakdown = document.getElementById("topic-breakdown");
    breakdown.innerHTML = "";
    const proportions = (spectrumEntry && spectrumEntry.topicProportions) || {};
    const orderedTopics = Object.entries(proportions).sort((a, b) => b[1] - a[1]);
    if (!orderedTopics.length) {
      breakdown.appendChild(el("p", "empty-state", "尚無足夠貼文計算議題細項。"));
    }
    orderedTopics.forEach(([topic, value]) => {
      const row = el("div", "topic-breakdown-row");

      const head = el("div", "topic-breakdown-head");
      const url = topicPageUrl(topic);
      const nameNode = el(url ? "a" : "span", "topic-breakdown-name", topic);
      if (url) {
        nameNode.href = url;
        nameNode.title = `看「${topic}」議題的候選人比較`;
      }
      head.appendChild(nameNode);
      head.appendChild(el("span", "data-date", `${Math.round(value * 100)}%`));
      row.appendChild(head);

      const track = el("div", "topic-breakdown-track");
      const fill = el("i");
      fill.style.width = `${Math.max(value * 100, 1.5).toFixed(1)}%`;
      fill.style.background = TOPIC_COLORS[topic] || "#9aa19d";
      track.appendChild(fill);
      row.appendChild(track);

      const keywordRows =
        (topicDetails && topicDetails.topics && topicDetails.topics[topic] && topicDetails.topics[topic][candidateId]) || [];
      if (keywordRows.length) {
        const chips = el("div", "entry-meta");
        keywordRows.slice(0, 6).forEach(([keyword, count]) => {
          chips.appendChild(el("span", "pill", `${keyword} ×${count}`));
        });
        row.appendChild(chips);
      }
      breakdown.appendChild(row);
    });

    const list = document.getElementById("post-list");
    const candidatesById = { [candidateId]: sourceEntry };
    const allPosts = posts;

    // Tri-state chip filters (none → include → exclude), same interaction
    // model as Harmonica-in-Taiwan's feed filter.
    const filterState = { topics: new Map(), intents: new Map() };

    const topicCounts = new Map();
    const intentCounts = new Map();
    allPosts.forEach((post) => {
      (post.topics || []).forEach((t) => topicCounts.set(t, (topicCounts.get(t) || 0) + 1));
      const intent = (post.postingIntent && post.postingIntent.type) || "self_initiated";
      intentCounts.set(intent, (intentCounts.get(intent) || 0) + 1);
    });
    const topicOptions = [...topicCounts.entries()].sort((a, b) => b[1] - a[1]);
    const intentOptions = Object.keys(INTENT_LABELS).map((key) => [key, intentCounts.get(key) || 0, INTENT_LABELS[key]]);

    function passes(post) {
      const groups = [
        [filterState.topics, post.topics || []],
        [filterState.intents, [(post.postingIntent && post.postingIntent.type) || "self_initiated"]],
      ];
      return groups.every(([states, values]) => {
        if (values.some((v) => states.get(v) === "exclude")) return false;
        const includes = [...states.entries()].filter(([, s]) => s === "include").map(([v]) => v);
        return !includes.length || values.some((v) => includes.includes(v));
      });
    }

    function renderTimeline() {
      const filtered = allPosts.filter(passes);
      document.getElementById("timeline-count").textContent = `顯示 ${filtered.length} / ${allPosts.length} 則`;
      list.innerHTML = "";
      if (!filtered.length) {
        list.appendChild(el("p", "empty-state", "沒有符合篩選條件的貼文。"));
        return;
      }
      createRiver(list, filtered, candidatesById);
    }

    function renderChipGroup(containerId, options, states) {
      const box = document.getElementById(containerId);
      box.innerHTML = "";
      options.forEach(([value, count, display]) => {
        const chip = el("button", "feed-option-chip", `${display || value}（${count}）`);
        chip.dataset.filterState = states.get(value) || "";
        chip.addEventListener("click", () => {
          const current = states.get(value);
          if (!current) states.set(value, "include");
          else if (current === "include") states.set(value, "exclude");
          else states.delete(value);
          renderFilters();
          renderTimeline();
        });
        box.appendChild(chip);
      });
    }

    function renderFilters() {
      renderChipGroup("timeline-topic-chips", topicOptions, filterState.topics);
      renderChipGroup("timeline-intent-chips", intentOptions, filterState.intents);
    }

    if (allPosts.length) {
      document.getElementById("timeline-filters").hidden = false;
      renderFilters();
    }
    renderTimeline();
  }

  function renderSources() {
    fetchJson("api/sources.json")
      .then((payload) => {
        const tableWrap = document.querySelector(".directory-table-list");
        let control = document.getElementById("source-sort-control");
        function renderTable() {
        if (control) control.remove();
        control = sortControl(renderTable);
        control.id = "source-sort-control";
        control.style.marginBottom = "12px";
        tableWrap.parentElement.insertBefore(control, tableWrap);

        const tbody = document.querySelector("#source-table tbody");
        tbody.innerHTML = "";
        document.getElementById("source-count").textContent = `${payload.count} 位候選人`;
        sortCandidates(payload.sources).forEach((source) => {
          const row = document.createElement("tr");

          const nameCell = document.createElement("td");
          nameCell.className = "directory-source-cell";
          const identity = el("a", "directory-source-identity");
          identity.href = `${source.id}/`;
          identity.style.textDecoration = "none";
          identity.style.color = "inherit";
          identity.appendChild(avatarNode(source, true));
          const nameBlock = el("span", "directory-source-name-block");
          nameBlock.appendChild(document.createTextNode(source.name));
          identity.appendChild(nameBlock);
          nameCell.appendChild(identity);
          row.appendChild(nameCell);

          const linkCell = document.createElement("td");
          linkCell.className = "directory-link-cell";
          source.accounts.forEach((account) => linkCell.appendChild(platformIconLink(account)));
          row.appendChild(linkCell);

          const dateCell = document.createElement("td");
          dateCell.textContent = formatRelative(source.latestPostAt) || "—";
          row.appendChild(dateCell);

          const cityCell = document.createElement("td");
          cityCell.textContent = source.cityLabel;
          row.appendChild(cityCell);

          const partyCell = document.createElement("td");
          partyCell.textContent = source.party || "未標註";
          row.appendChild(partyCell);

          tbody.appendChild(row);
        });
        }

        renderTable();
      })
      .catch((err) => {
        document.querySelector("#source-table tbody").innerHTML = `<tr><td colspan="5">資料載入失敗：${err.message}</td></tr>`;
      });
  }

  function renderSourceDetail() {
    const candidateId = body.dataset.candidateId;
    Promise.all([
      fetchJson("api/sources.json"),
      fetchJson(`api/posts/${candidateId}.json`),
      fetchJson("api/spectrum.json"),
      fetchJson("api/topic-details.json").catch(() => null),
    ])
      .then(([sourcesPayload, postsPayload, spectrumPayload, topicDetails]) => {
        const source = sourcesPayload.sources.find((s) => s.id === candidateId);
        if (!source) throw new Error(`unknown candidate ${candidateId}`);

        document.getElementById("candidate-city").textContent = `${source.cityLabel}市長候選人`;
        document.getElementById("candidate-name").textContent = source.name;
        document.getElementById("candidate-party").textContent = `${source.party || "未標註"} · 已收錄 ${source.postCount} 則公開貼文`;
        const heroAvatar = document.getElementById("hero-avatar");
        heroAvatar.replaceWith(Object.assign(avatarNode(source, false), { id: "hero-avatar", className: "source-avatar source-hero-avatar" }));

        // Per-account post count + last update, from the candidate's own
        // posts (each carries the source_id of the account it came from) —
        // no separate API needed.
        const postsByAccount = new Map();
        postsPayload.posts.forEach((post) => {
          const bucket = postsByAccount.get(post.sourceId);
          if (bucket) {
            bucket.count += 1;
            if (!bucket.latest || post.postedAt > bucket.latest) bucket.latest = post.postedAt;
          } else {
            postsByAccount.set(post.sourceId, { count: 1, latest: post.postedAt });
          }
        });

        const accountBody = document.querySelector("#account-table tbody");
        source.accounts.forEach((account) => {
          const row = document.createElement("tr");

          const platformCell = document.createElement("td");
          const badge = platformIconLink(account);
          platformCell.appendChild(badge);
          platformCell.appendChild(document.createTextNode(" " + (PLATFORM_LABELS[account.platform] || account.platform)));
          row.appendChild(platformCell);

          const handleCell = document.createElement("td");
          const handleLink = el("a", "score-source-link", account.url);
          handleLink.href = account.url;
          handleLink.target = "_blank";
          handleLink.rel = "noopener";
          handleLink.title = account.url;
          handleCell.appendChild(handleLink);
          row.appendChild(handleCell);

          const stats = postsByAccount.get(account.id);
          const countCell = document.createElement("td");
          countCell.textContent = stats ? String(stats.count) : "0";
          row.appendChild(countCell);

          const updatedCell = document.createElement("td");
          updatedCell.textContent = (stats && formatRelative(stats.latest)) || "—";
          row.appendChild(updatedCell);

          accountBody.appendChild(row);
        });

        renderCandidateAnalytics({
          candidateId,
          sourceEntry: source,
          posts: postsPayload.posts,
          spectrumPayload,
          topicDetails,
        });
      })
      .catch((err) => {
        document.getElementById("post-list").textContent = `資料載入失敗：${err.message}`;
      });
  }

  // Mirrors classify_topics.TOPIC_SLUGS — per-topic page URLs.
  const TOPIC_SLUGS = {
    交通: "transport",
    住宅: "housing",
    社福: "welfare",
    環境: "environment",
    教育: "education",
    經濟: "economy",
    治安: "safety",
    醫療: "health",
    競選: "campaign",
    體育: "sports",
    文化觀光: "culture",
    兩岸外交: "cross-strait",
    防災: "disaster",
    議會監督: "oversight",
    生活: "life",
  };

  function topicPageUrl(topic) {
    const slug = TOPIC_SLUGS[topic];
    return slug ? `${base}spectrum/${slug}/` : null;
  }

  // Neutral candidate orderings. A fixed order (e.g. CSV / party order)
  // reads as an editorial stance, so co-listings sort by a data metric and
  // the default rotates randomly per page load.
  const NEUTRAL_SORTS = [
    {
      id: "latest",
      label: "最新更新",
      cmp: (a, b) => String(b.latestPostAt || "").localeCompare(String(a.latestPostAt || "")),
    },
    {
      id: "count",
      label: "貼文數",
      cmp: (a, b) => (b.postCount || 0) - (a.postCount || 0),
    },
  ];
  let activeSort = NEUTRAL_SORTS[Math.floor(Math.random() * NEUTRAL_SORTS.length)];

  function sortCandidates(list) {
    return [...list].sort(activeSort.cmp);
  }

  // Small "排序：..." control; onChange re-renders the caller's view.
  function sortControl(onChange) {
    const wrap = el("div", "sort-control");
    wrap.appendChild(el("span", "data-date", "排序："));
    wrap.title = "預設排序方式於每次載入時隨機選擇，避免固定順序暗示立場";
    NEUTRAL_SORTS.forEach((sort) => {
      const chip = el("button", "feed-option-chip", sort.label);
      chip.dataset.filterState = activeSort.id === sort.id ? "include" : "";
      chip.addEventListener("click", () => {
        activeSort = sort;
        onChange();
      });
      wrap.appendChild(chip);
    });
    return wrap;
  }

  // Shared topic palette — same order/colors as the candidate-page pie chart.
  const TOPIC_COLORS = {
    交通: "#0f766e",
    住宅: "#b87921",
    社福: "#c85f44",
    環境: "#4d8a56",
    教育: "#3b6ea5",
    經濟: "#7c5cad",
    治安: "#a54d68",
    醫療: "#5c6a63",
    競選: "#d46a9e",
    體育: "#45a0c9",
    文化觀光: "#c9a227",
    兩岸外交: "#8a5a2d",
    防災: "#e07b39",
    議會監督: "#7a7f2a",
    生活: "#b8bdb9",
  };

  function renderSpectrum() {
    Promise.all([fetchJson("api/cities.json"), fetchJson("api/sources.json"), fetchJson("api/topic-index.json")])
      .then(([citiesPayload, sourcesPayload, topicIndex]) => {
        const sourcesById = Object.fromEntries(sourcesPayload.sources.map((s) => [s.id, s]));
        const fallbackTopic = topicIndex.fallbackTopic;
        const allTopics = Object.keys(TOPIC_COLORS);
        const allIntents = Object.keys(INTENT_LABELS);
        const intentCounts = Object.fromEntries(allIntents.map((intent) => [intent, 0]));
        topicIndex.posts.forEach((post) => {
          const intent = post.postingIntent || "self_initiated";
          intentCounts[intent] = (intentCounts[intent] || 0) + 1;
        });

        const state = {
          rangeDays: null, // null = 全部
          excluded: new Set([fallbackTopic]),
          excludedIntents: new Set(),
        };

        const RANGES = [
          ["全部", null],
          ["近 30 天", 30],
          ["近 14 天", 14],
          ["近 7 天", 7],
        ];

        function computeSpectrum() {
          const cutoff = state.rangeDays ? Date.now() - state.rangeDays * 86400e3 : null;
          const perCandidate = {};
          topicIndex.posts.forEach((post) => {
            if (state.excludedIntents.has(post.postingIntent || "self_initiated")) return;
            if (cutoff) {
              const at = post.postedAt ? Date.parse(post.postedAt) : NaN;
              if (Number.isNaN(at) || at < cutoff) return;
            }
            const bucket = (perCandidate[post.candidateId] ||= { totals: {}, count: 0 });
            let counted = false;
            Object.entries(post.topicScores || {}).forEach(([topic, score]) => {
              if (state.excluded.has(topic)) return;
              bucket.totals[topic] = (bucket.totals[topic] || 0) + score;
              counted = true;
            });
            if (counted) bucket.count += 1;
          });
          const result = {};
          Object.entries(perCandidate).forEach(([candidateId, bucket]) => {
            const grand = Object.values(bucket.totals).reduce((a, b) => a + b, 0);
            const proportions = {};
            if (grand > 0) {
              Object.entries(bucket.totals).forEach(([topic, value]) => {
                proportions[topic] = value / grand;
              });
            }
            result[candidateId] = { proportions, count: bucket.count };
          });
          return result;
        }

        function renderChips() {
          const rangeChips = document.getElementById("range-chips");
          rangeChips.innerHTML = "";
          RANGES.forEach(([label, days]) => {
            const chip = el("button", "feed-option-chip", label);
            chip.dataset.filterState = (state.rangeDays === days ? "include" : "");
            chip.addEventListener("click", () => {
              state.rangeDays = days;
              renderChips();
              renderTable();
            });
            rangeChips.appendChild(chip);
          });

          const topicChips = document.getElementById("topic-chips");
          topicChips.innerHTML = "";
          allTopics.forEach((topic) => {
            const chip = el("button", "feed-option-chip", topic);
            chip.dataset.filterState = state.excluded.has(topic) ? "exclude" : "include";
            chip.title = state.excluded.has(topic) ? "已排除，點擊恢復" : "點擊排除";
            chip.addEventListener("click", () => {
              if (state.excluded.has(topic)) state.excluded.delete(topic);
              else state.excluded.add(topic);
              renderChips();
              renderTable();
            });
            topicChips.appendChild(chip);
          });

          const intentChips = document.getElementById("intent-chips");
          intentChips.innerHTML = "";
          allIntents.forEach((intent) => {
            const excluded = state.excludedIntents.has(intent);
            const chip = el("button", "feed-option-chip", `${INTENT_LABELS[intent]} ${intentCounts[intent] || 0}`);
            chip.dataset.filterState = excluded ? "exclude" : "include";
            chip.title = excluded ? "已排除，點擊恢復" : "點擊排除";
            chip.addEventListener("click", () => {
              if (excluded) state.excludedIntents.delete(intent);
              else state.excludedIntents.add(intent);
              renderChips();
              renderTable();
            });
            intentChips.appendChild(chip);
          });

          let sortGroup = document.getElementById("spectrum-sort-group");
          if (!sortGroup) {
            sortGroup = el("div", "spectrum-control-group");
            sortGroup.id = "spectrum-sort-group";
            document.querySelector(".spectrum-controls").appendChild(sortGroup);
          }
          sortGroup.innerHTML = "";
          sortGroup.appendChild(
            sortControl(() => {
              renderChips();
              renderTable();
            })
          );
        }

        const container = document.getElementById("spectrum-cities");

        function renderTable() {
        const spectrum = computeSpectrum();
        const spectrumById = {};
        Object.entries(spectrum).forEach(([candidateId, entry]) => {
          spectrumById[candidateId] = { topicProportions: entry.proportions, filteredCount: entry.count };
        });

        // Fixed topic column order = overall volume across all candidates,
        // so the most-discussed issues sit left and every row is comparable.
        const totals = {};
        Object.values(spectrumById).forEach((entry) => {
          Object.entries(entry.topicProportions || {}).forEach(([topic, value]) => {
            totals[topic] = (totals[topic] || 0) + value;
          });
        });
        const topics = Object.keys(totals).sort((a, b) => totals[b] - totals[a]);

        container.innerHTML = "";
        if (!topics.length) {
          container.appendChild(el("p", "empty-state", "目前的篩選條件下沒有任何議題資料。"));
          return;
        }

        const wrap = el("div", "directory-table-list");
        const table = el("table", "score-table spectrum-table");
        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        headRow.appendChild(el("th", "", "候選人"));
        topics.forEach((topic) => {
          const th = el("th", "spectrum-topic-head");
          const url = topicPageUrl(topic);
          if (url) {
            const link = el("a", "spectrum-topic-link", topic);
            link.href = url;
            link.title = `看「${topic}」議題的候選人比較`;
            th.appendChild(link);
          } else {
            th.textContent = topic;
          }
          headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        table.appendChild(thead);
        const tbody = document.createElement("tbody");

        citiesPayload.cities.forEach((city) => {
          if (!city.candidateIds.length) return;
          const cityRow = document.createElement("tr");
          const cityCell = el("td", "spectrum-city-cell", city.label);
          cityCell.colSpan = topics.length + 1;
          cityRow.appendChild(cityCell);
          tbody.appendChild(cityRow);

          sortCandidates(city.candidateIds.map((id) => sourcesById[id]).filter(Boolean)).forEach((source) => {
            const candidateId = source.id;
            const entry = spectrumById[candidateId];
            const proportions = (entry && entry.topicProportions) || {};
            const rowMax = Math.max(0, ...Object.values(proportions));

            const row = document.createElement("tr");
            const nameCell = document.createElement("td");
            nameCell.className = "directory-source-cell";
            const identity = el("a", "spectrum-identity");
            identity.href = `../source/${source.id}/`;
            identity.appendChild(avatarNode(source, true));
            const nameWrap = el("div");
            nameWrap.appendChild(el("strong", "", source.name));
            nameWrap.appendChild(el("span", "data-date", `${source.party || "未標註"} · ${source.postCount} 則`));
            identity.appendChild(nameWrap);
            nameCell.appendChild(identity);
            row.appendChild(nameCell);

            topics.forEach((topic) => {
              const value = proportions[topic] || 0;
              const cell = el("td", "spectrum-cell");
              if (!Object.keys(proportions).length) {
                cell.textContent = "—";
                cell.style.color = "var(--muted)";
              } else if (value > 0) {
                cell.textContent = `${Math.round(value * 100)}%`;
                // Shade by intensity; highlight each candidate's strongest topic.
                cell.style.background = `rgba(15, 118, 110, ${(0.08 + 0.72 * (value / (rowMax || 1))).toFixed(3)})`;
                if (value / (rowMax || 1) > 0.55) cell.style.color = "#fff";
                if (value === rowMax) cell.classList.add("spectrum-cell-max");
              } else {
                cell.textContent = "·";
                cell.style.color = "#c4ccc6";
              }
              row.appendChild(cell);
            });
            tbody.appendChild(row);
          });
        });

        table.appendChild(tbody);
        wrap.appendChild(table);
        container.appendChild(wrap);

        const note = el("p", "data-date", "顏色深淺＝該議題佔該候選人議題發文的比例（每列各自正規化）；粗框＝該候選人聲量最高的議題；「·」＝無相關貼文。點表頭議題名稱可看該議題的跨候選人比較。");
        note.style.marginTop = "12px";
        container.appendChild(note);
        }

        renderChips();
        renderTable();
      })
      .catch((err) => {
        document.getElementById("spectrum-cities").textContent = `資料載入失敗：${err.message}`;
      });
  }

  function renderTopicDetail() {
    const topic = body.dataset.topic;
    Promise.all([fetchJson("api/sources.json"), fetchJson("api/topic-details.json"), fetchJson("api/topic-index.json")])
      .then(([sourcesPayload, details, topicIndex]) => {
        const sourcesById = Object.fromEntries(sourcesPayload.sources.map((s) => [s.id, s]));
        const keywordsByCandidate = (details.topics || {})[topic] || {};

        // Which candidates have posts on this topic, ordered by volume.
        const postIdsByCandidate = {};
        topicIndex.posts.forEach((post) => {
          if (post.topicScores && post.topicScores[topic]) {
            (postIdsByCandidate[post.candidateId] ||= new Set()).add(post.id);
          }
        });
        const candidateIds = Object.keys(postIdsByCandidate).sort(
          (a, b) => postIdsByCandidate[b].size - postIdsByCandidate[a].size
        );

        const totalPosts = candidateIds.reduce((sum, id) => sum + postIdsByCandidate[id].size, 0);
        document.getElementById("topic-summary").textContent =
          `${candidateIds.length} 位候選人共 ${totalPosts} 則相關貼文。可複選候選人縮小比較範圍，或直接看全部並排比較。`;

        const container = document.getElementById("topic-candidates");
        container.innerHTML = "";
        if (!candidateIds.length) {
          container.appendChild(el("p", "empty-state", "目前沒有這個議題的貼文。"));
          return;
        }

        // Candidate picker: pick one or more candidates to narrow the view
        // instead of scrolling through every section. Empty selection = show
        // everyone.
        const selectedIds = new Set();
        const picker = el("div", "feed-option-chips topic-candidate-picker");
        container.appendChild(picker);
        const sectionsWrap = el("div");
        container.appendChild(sectionsWrap);

        function renderPicker() {
          picker.innerHTML = "";
          const allChip = el("button", "feed-option-chip", "全部");
          allChip.dataset.filterState = selectedIds.size === 0 ? "include" : "";
          allChip.title = "清除選取，顯示所有候選人";
          allChip.addEventListener("click", () => {
            selectedIds.clear();
            renderPicker();
            renderSections();
          });
          picker.appendChild(allChip);

          candidateIds.forEach((candidateId) => {
            const source = sourcesById[candidateId];
            if (!source) return;
            const chip = el("button", "feed-option-chip topic-candidate-chip");
            chip.dataset.filterState = selectedIds.has(candidateId) ? "include" : "";
            chip.appendChild(avatarNode(source, true));
            chip.appendChild(document.createTextNode(` ${source.name}（${postIdsByCandidate[candidateId].size}）`));
            chip.addEventListener("click", () => {
              if (selectedIds.has(candidateId)) selectedIds.delete(candidateId);
              else selectedIds.add(candidateId);
              renderPicker();
              renderSections();
            });
            picker.appendChild(chip);
          });
        }

        // Topic posts per candidate, fetched once and cached.
        const topicPostsCache = new Map();
        function topicPosts(candidateId) {
          if (!topicPostsCache.has(candidateId)) {
            topicPostsCache.set(
              candidateId,
              fetchJson(`api/posts/${candidateId}.json`).then((payload) => {
                const wanted = postIdsByCandidate[candidateId];
                return payload.posts.filter((p) => wanted.has(p.id));
              })
            );
          }
          return topicPostsCache.get(candidateId);
        }

        function candidateHeading(candidateId) {
          const source = sourcesById[candidateId];
          const heading = el("div", "topic-candidate-heading");
          const identity = el("a", "spectrum-identity");
          identity.href = `${base}source/${source.id}/`;
          identity.appendChild(avatarNode(source, true));
          const nameWrap = el("div");
          nameWrap.appendChild(el("strong", "", source.name));
          nameWrap.appendChild(
            el("span", "data-date", `${source.cityLabel} · ${source.party || "未標註"} · 本議題 ${postIdsByCandidate[candidateId].size} 則`)
          );
          identity.appendChild(nameWrap);
          heading.appendChild(identity);

          const keywords = keywordsByCandidate[candidateId] || [];
          if (keywords.length) {
            const chipRow = el("div", "entry-meta");
            keywords.slice(0, 8).forEach(([keyword, count]) => {
              chipRow.appendChild(el("span", "pill", `${keyword} ×${count}`));
            });
            heading.appendChild(chipRow);
          }
          return heading;
        }

        function renderSections() {
          sectionsWrap.innerHTML = "";

          // Empty selection = everyone; otherwise only the picked candidates,
          // in the same order the picker lists them (already sorted by
          // volume for this topic).
          const shownIds = selectedIds.size ? candidateIds.filter((id) => selectedIds.has(id)) : candidateIds;

          const summaryBlock = el("div", "topic-summaries");
          shownIds.forEach((candidateId) => summaryBlock.appendChild(candidateHeading(candidateId)));
          sectionsWrap.appendChild(summaryBlock);

          const wallTitle = el("p", "section-kicker", "Posts");
          wallTitle.style.marginTop = "28px";
          sectionsWrap.appendChild(wallTitle);
          sectionsWrap.appendChild(el("h2", "", shownIds.length === candidateIds.length ? "全部貼文" : "選取的貼文"));

          const list = el("div", "latest-feed-grid");
          list.textContent = "載入貼文中...";
          list.style.marginTop = "14px";
          sectionsWrap.appendChild(list);

          Promise.all(shownIds.map((id) => topicPosts(id))).then((groups) => {
            const merged = groups.flat().sort((a, b) => (b.postedAt || "").localeCompare(a.postedAt || ""));
            list.textContent = "";
            createRiver(list, merged, sourcesById);
          });
        }

        renderPicker();
        renderSections();
      })
      .catch((err) => {
        document.getElementById("topic-candidates").textContent = `資料載入失敗：${err.message}`;
      });
  }

  function renderPolicyMatch() {
    Promise.all([fetchJson("api/policy-match.json"), fetchJson("api/sources.json")]).then(([data, sources]) => {
      const sourceById = Object.fromEntries(sources.sources.map((s) => [s.id, s]));
      const wrap = document.getElementById("policy-questions");
      const selections = new Map(data.questions.map((question) => [question.id, new Set()]));
      wrap.innerHTML = "";
      data.questions.forEach((question) => {
        const block = el("section", "policy-question");
        const selected = selections.get(question.id);
        block.appendChild(el("h2", "", question.prompt));
        block.appendChild(el("p", "data-date", `最多選 ${question.maxChoices} 項`));
        const choices = el("div", "policy-choice-grid");
        question.choices.forEach((choice) => {
          const button = el("button", "policy-choice", choice.label);
          button.addEventListener("click", () => {
            if (selected.has(choice.id)) selected.delete(choice.id);
            else if (selected.size < question.maxChoices) selected.add(choice.id);
            button.dataset.selected = selected.has(choice.id) ? "true" : "false";
          });
          choices.appendChild(button);
        });
        block.appendChild(choices);
        wrap.appendChild(block);
      });
      const submit = el("button", "feed-load-more-button policy-submit", "查看匹配結果");
      wrap.appendChild(submit);
      wrap.appendChild(el("p", "data-date", data.methodology));
      submit.addEventListener("click", () => {
        const results = document.getElementById("policy-results");
        results.hidden = false;
        results.innerHTML = "";
        const selectedIds = [...selections.values()].flatMap((values) => [...values]);
        if (!selectedIds.length) { results.appendChild(el("p", "empty-state", "請先選擇至少一項政策。")); return; }
        const choiceMap = Object.fromEntries(data.questions.flatMap((q) => q.choices).map((c) => [c.id, c]));
        const topics = [...new Set(selectedIds.flatMap((id) => choiceMap[id].topics))];
        results.appendChild(el("h2", "", "與你的市政優先順序最接近"));
        results.appendChild(el("p", "feed-page-summary", "相似度只反映候選人自主政策倡議貼文的議題分布；貼文太少者標示資料不足，不代表候選人反對該政策。"));
        const byCity = {};
        data.candidates.forEach((candidate) => {
          const targetNorm = Math.sqrt(topics.length);
          const candidateNorm = Math.sqrt(Object.values(candidate.topicWeights).reduce((sum, value) => sum + value * value, 0));
          const dot = topics.reduce((sum, topic) => sum + (candidate.topicWeights[topic] || 0), 0);
          const score = candidateNorm ? dot / (targetNorm * candidateNorm) : 0;
          (byCity[candidate.city] ||= []).push({ ...candidate, score });
        });
        Object.values(byCity).forEach((rows) => {
          rows.sort((a, b) => b.score - a.score);
          const city = sourceById[rows[0].candidateId] && sourceById[rows[0].candidateId].cityLabel;
          results.appendChild(el("h3", "policy-city-title", city || rows[0].city));
          const grid = el("div", "directory-grid");
          rows.forEach((row) => {
            const card = el("article", "home-feed-card policy-result-card");
            const source = sourceById[row.candidateId] || row;
            const head = el("a", "candidate-city-identity"); head.href = `${base}source/${row.candidateId}/`;
            head.appendChild(avatarNode(source, true)); head.appendChild(el("strong", "", row.candidateName)); card.appendChild(head);
            card.appendChild(el("strong", "policy-score", row.eligiblePostCount ? `${Math.round(row.score * 100)}% 議題重合` : "資料不足"));
            card.appendChild(el("p", "data-date", `依 ${row.eligiblePostCount} 則自主政策倡議貼文計算`));
            const evidence = topics.flatMap((topic) => (row.evidence[topic] || []).map((item) => ({ ...item, topic }))).slice(0, 3);
            evidence.forEach((item) => { const link = el("a", "policy-evidence", `${item.topic}：${item.text}`); link.href = item.url; link.target = "_blank"; link.rel = "noopener"; card.appendChild(link); });
            grid.appendChild(card);
          });
          results.appendChild(grid);
        });
      });
    }).catch((err) => { document.getElementById("policy-questions").textContent = `資料載入失敗：${err.message}`; });
  }

  // /status/ is now rendered server-side by build_status_page.py (it needs
  // live collector health data — RSSHub probe, Apify pacing check, etc. —
  // that only make sense to compute at build time).

  if (body.dataset.page === "index") {
    renderIndex();
  } else if (body.dataset.page === "sources") {
    renderSources();
  } else if (body.dataset.page === "source-detail") {
    renderSourceDetail();
  } else if (body.dataset.page === "spectrum") {
    renderSpectrum();
  } else if (body.dataset.page === "topic-detail") {
    renderTopicDetail();
  } else if (body.dataset.page === "policy-match") {
    renderPolicyMatch();
  }
})();
