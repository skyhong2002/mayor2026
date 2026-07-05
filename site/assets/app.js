(function () {
  const body = document.body;
  const base = body.dataset.base || "";
  const FEED_PAGE_SIZE = 30;

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

  const ROLE_LABELS = {
    campaign: "競選帳號",
    personal: "個人帳號",
    incumbent: "現任市政帳號",
    party: "政黨帳號",
    affiliated: "周邊社群",
  };

  const VERIFICATION_LABELS = {
    first_party: "一手驗證",
    cross_ref: "交叉驗證",
    unverified: "未完全驗證",
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
      post.topics.forEach((topic) => meta.appendChild(el("span", "pill", topic)));
      card.appendChild(meta);
    }

    const footer = el("div", "home-feed-footer");
    footer.appendChild(el("p", "entry-meta data-date", formatDate(post.postedAt)));
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
        if (latestAt) document.getElementById("data-date").textContent = `最後更新 ${formatDate(latestAt)}`;

        const grid = document.getElementById("city-grid");
        grid.innerHTML = "";
        citiesPayload.cities.forEach((city) => {
          const card = el("article", "home-feed-card city-card");
          card.appendChild(el("h3", "city-card-title", city.label));

          if (!city.candidateIds.length) {
            card.appendChild(el("p", "empty-state", "尚無候選人資料"));
          } else {
            const list = el("div", "candidate-city-list");
            city.candidateIds.forEach((candidateId) => {
              const candidate = candidatesById[candidateId];
              if (!candidate) return;
              const link = el("a");
              link.href = `${city.id}/${candidate.id}/`;
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

  function renderCandidate() {
    const candidateId = body.dataset.candidateId;
    Promise.all([fetchJson(`api/posts/${candidateId}.json`), fetchJson("api/spectrum.json"), fetchJson("api/sources.json")])
      .then(([postsPayload, spectrumPayload, sourcesPayload]) => {
        const candidate = postsPayload.candidate;
        const sourceEntry = sourcesPayload.sources.find((s) => s.id === candidateId) || candidate;
        document.getElementById("candidate-city").textContent = candidate.cityLabel;
        document.getElementById("candidate-name").textContent = candidate.name;
        document.getElementById("candidate-party").textContent = `${candidate.party || "未標註"} · 已收錄 ${postsPayload.count} 則公開貼文`;

        const linksEl = document.getElementById("candidate-links");
        Object.entries(candidate.links || {}).forEach(([platform, url]) => {
          if (!url) return;
          const a = el("a", "secondary-link", PLATFORM_LABELS[platform] || platform);
          a.href = url;
          a.target = "_blank";
          a.rel = "noopener";
          linksEl.appendChild(a);
        });

        const spectrumEntry = spectrumPayload.candidates.find((c) => c.candidateId === candidateId);
        renderTopicChart(document.getElementById("topic-chart"), spectrumEntry ? spectrumEntry.topicProportions : {});

        const list = document.getElementById("post-list");
        list.innerHTML = "";
        const candidatesById = { [candidate.id]: sourceEntry };
        createRiver(list, postsPayload.posts, candidatesById);
      })
      .catch((err) => {
        document.getElementById("post-list").textContent = `資料載入失敗：${err.message}`;
      });
  }

  function renderSources() {
    fetchJson("api/sources.json")
      .then((payload) => {
        const tbody = document.querySelector("#source-table tbody");
        tbody.innerHTML = "";
        document.getElementById("source-count").textContent = `${payload.count} 位候選人`;
        payload.sources.forEach((source) => {
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
          dateCell.textContent = formatDate(source.latestPostAt) || "—";
          row.appendChild(dateCell);

          const cityCell = document.createElement("td");
          cityCell.textContent = source.cityLabel;
          row.appendChild(cityCell);

          const partyCell = document.createElement("td");
          partyCell.textContent = source.party || "未標註";
          row.appendChild(partyCell);

          tbody.appendChild(row);
        });
      })
      .catch((err) => {
        document.querySelector("#source-table tbody").innerHTML = `<tr><td colspan="5">資料載入失敗：${err.message}</td></tr>`;
      });
  }

  function renderSourceDetail() {
    const candidateId = body.dataset.candidateId;
    Promise.all([fetchJson("api/sources.json"), fetchJson(`api/posts/${candidateId}.json`)])
      .then(([sourcesPayload, postsPayload]) => {
        const source = sourcesPayload.sources.find((s) => s.id === candidateId);
        if (!source) throw new Error(`unknown candidate ${candidateId}`);

        document.getElementById("candidate-city").textContent = `${source.cityLabel}市長候選人`;
        document.getElementById("candidate-name").textContent = source.name;
        document.getElementById("candidate-party").textContent = `${source.party || "未標註"} · 已收錄 ${source.postCount} 則公開貼文`;
        const heroAvatar = document.getElementById("hero-avatar");
        heroAvatar.replaceWith(Object.assign(avatarNode(source, false), { id: "hero-avatar", className: "source-avatar source-hero-avatar" }));

        const infoBody = document.querySelector("#info-table tbody");
        [
          ["城市", source.cityLabel],
          ["政黨", source.party || "未標註"],
          ["監看帳號數", String(source.accounts.length)],
          ["最後更新", formatDate(source.latestPostAt) || "尚無貼文"],
        ].forEach(([label, value]) => {
          const row = document.createElement("tr");
          const th = document.createElement("th");
          th.textContent = label;
          th.style.width = "180px";
          const td = document.createElement("td");
          td.textContent = value;
          row.appendChild(th);
          row.appendChild(td);
          infoBody.appendChild(row);
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

          const roleCell = document.createElement("td");
          roleCell.textContent = ROLE_LABELS[account.role] || account.role || "—";
          row.appendChild(roleCell);

          const verifyCell = document.createElement("td");
          verifyCell.textContent = VERIFICATION_LABELS[account.verification] || account.verification || "—";
          row.appendChild(verifyCell);

          accountBody.appendChild(row);
        });

        const list = document.getElementById("post-list");
        list.innerHTML = "";
        createRiver(list, postsPayload.posts, { [source.id]: source });
      })
      .catch((err) => {
        document.getElementById("post-list").textContent = `資料載入失敗：${err.message}`;
      });
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
  };

  function renderSpectrum() {
    Promise.all([fetchJson("api/cities.json"), fetchJson("api/sources.json"), fetchJson("api/spectrum.json")])
      .then(([citiesPayload, sourcesPayload, spectrumPayload]) => {
        const sourcesById = Object.fromEntries(sourcesPayload.sources.map((s) => [s.id, s]));
        const spectrumById = Object.fromEntries(spectrumPayload.candidates.map((c) => [c.candidateId, c]));

        const legend = document.getElementById("spectrum-legend");
        Object.entries(TOPIC_COLORS).forEach(([topic, color]) => {
          const item = el("span");
          const swatch = el("i");
          swatch.style.background = color;
          item.appendChild(swatch);
          item.appendChild(document.createTextNode(topic));
          legend.appendChild(item);
        });

        const container = document.getElementById("spectrum-cities");
        container.innerHTML = "";
        citiesPayload.cities.forEach((city) => {
          if (!city.candidateIds.length) return;
          const section = el("div", "spectrum-city");
          const kicker = el("p", "section-kicker", city.id.replace("-", " ").toUpperCase());
          section.appendChild(kicker);
          section.appendChild(el("h2", "", city.label));

          city.candidateIds.forEach((candidateId) => {
            const source = sourcesById[candidateId];
            if (!source) return;
            const entry = spectrumById[candidateId];
            const proportions = (entry && entry.topicProportions) || {};

            const row = el("div", "spectrum-row");

            const identity = el("a", "spectrum-identity");
            identity.href = `../${source.city}/${source.id}/`;
            identity.appendChild(avatarNode(source, true));
            const nameWrap = el("div");
            nameWrap.appendChild(el("strong", "", source.name));
            nameWrap.appendChild(el("span", "data-date", `${source.party || "未標註"} · ${source.postCount} 則`));
            identity.appendChild(nameWrap);
            row.appendChild(identity);

            const topics = Object.entries(proportions).sort((a, b) => b[1] - a[1]);
            if (!topics.length) {
              const emptyBar = el("div", "spectrum-bar spectrum-bar-empty", "尚無足夠貼文計算議題比例");
              row.appendChild(emptyBar);
            } else {
              const bar = el("div", "spectrum-bar");
              topics.forEach(([topic, value]) => {
                const segment = el("i");
                segment.style.width = `${(value * 100).toFixed(2)}%`;
                segment.style.background = TOPIC_COLORS[topic] || "#9aa19d";
                segment.title = `${topic} ${(value * 100).toFixed(1)}%`;
                bar.appendChild(segment);
              });
              row.appendChild(bar);
            }

            const dominant = el("div", "spectrum-dominant");
            if (entry && entry.dominantTopic) {
              const pill = el("span", "pill", `主要：${entry.dominantTopic}`);
              pill.style.background = "rgba(15, 118, 110, 0.12)";
              pill.style.color = "var(--accent-strong, #0a514d)";
              dominant.appendChild(pill);
            } else {
              dominant.textContent = "—";
            }
            row.appendChild(dominant);

            section.appendChild(row);
          });
          container.appendChild(section);
        });
      })
      .catch((err) => {
        document.getElementById("spectrum-cities").textContent = `資料載入失敗：${err.message}`;
      });
  }

  function renderStatus() {
    const STEP_LABELS = { ok: "成功", failed: "失敗", optional_failed: "失敗（非必要）", running: "執行中", pending: "等待中" };
    Promise.all([
      fetchJson("api/status.json"),
      fetchJson("api/pipeline-runtime.json").catch(() => null),
    ])
      .then(([status, runtime]) => {
        const metrics = status.metrics || {};
        document.getElementById("status-summary").textContent =
          `資料產生於 ${formatDate(status.generatedAt)}；最新收錄貼文 ${formatDate(metrics.latestPostAt) || "—"}。`;

        const metricRow = document.getElementById("metric-row");
        const cells = [
          [String(metrics.candidates ?? "—"), "監看候選人"],
          [String(metrics.watchAccounts ?? "—"), "監看帳號"],
          [String(metrics.totalPosts ?? "—"), "已收錄貼文"],
        ];
        Object.entries(metrics.postsByPlatform || {}).forEach(([platform, count]) => {
          cells.push([String(count), PLATFORM_LABELS[platform] || platform]);
        });
        metricRow.innerHTML = "";
        cells.forEach(([value, label]) => {
          const cell = el("div", "stat-card");
          cell.style.color = "var(--ink)";
          cell.style.background = "#eef4f0";
          cell.style.border = "1px solid var(--line)";
          cell.appendChild(el("strong", "", value));
          cell.appendChild(Object.assign(el("span", "", label), { style: "color: var(--muted)" }));
          metricRow.appendChild(cell);
        });

        const pipelineBody = document.querySelector("#pipeline-table tbody");
        pipelineBody.innerHTML = "";
        const steps = (runtime && runtime.steps) || [];
        if (!steps.length) {
          pipelineBody.innerHTML = '<tr><td colspan="4">尚無執行紀錄。</td></tr>';
        }
        steps.forEach((step) => {
          const row = document.createElement("tr");
          [step.name, STEP_LABELS[step.status] || step.status, formatDate(step.startedAt) || "—", formatDate(step.finishedAt) || "—"].forEach(
            (value) => {
              const td = document.createElement("td");
              td.textContent = value;
              row.appendChild(td);
            }
          );
          pipelineBody.appendChild(row);
        });

        const errorBody = document.querySelector("#error-table tbody");
        errorBody.innerHTML = "";
        const errors = status.recentErrors || [];
        if (!errors.length) {
          errorBody.innerHTML = '<tr><td colspan="3">近期沒有抓取錯誤。</td></tr>';
        }
        errors.slice().reverse().forEach((error) => {
          const row = document.createElement("tr");
          [error.sourceId || "—", error.message || "—", formatDate(error.recordedAt) || "—"].forEach((value) => {
            const td = document.createElement("td");
            td.textContent = value;
            td.style.whiteSpace = "normal";
            row.appendChild(td);
          });
          errorBody.appendChild(row);
        });
      })
      .catch((err) => {
        document.getElementById("status-summary").textContent = `資料載入失敗：${err.message}`;
      });
  }

  if (body.dataset.page === "index") {
    renderIndex();
  } else if (body.dataset.page === "candidate") {
    renderCandidate();
  } else if (body.dataset.page === "sources") {
    renderSources();
  } else if (body.dataset.page === "source-detail") {
    renderSourceDetail();
  } else if (body.dataset.page === "status") {
    renderStatus();
  } else if (body.dataset.page === "spectrum") {
    renderSpectrum();
  }
})();
