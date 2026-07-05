(function () {
  const body = document.body;
  const base = body.dataset.base || "";

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

  function renderIndex() {
    Promise.all([fetchJson("api/cities.json"), fetchJson("api/candidates.json")])
      .then(([citiesPayload, candidatesPayload]) => {
        const candidatesById = Object.fromEntries(candidatesPayload.candidates.map((c) => [c.id, c]));
        const grid = document.getElementById("city-grid");
        grid.innerHTML = "";
        citiesPayload.cities.forEach((city) => {
          const card = document.createElement("div");
          card.className = "city-card";
          const heading = document.createElement("h2");
          heading.textContent = city.label;
          card.appendChild(heading);

          if (city.candidateIds.length === 0) {
            const empty = document.createElement("p");
            empty.className = "empty-state";
            empty.textContent = "尚無候選人資料";
            card.appendChild(empty);
          }

          city.candidateIds.forEach((candidateId) => {
            const candidate = candidatesById[candidateId];
            if (!candidate) return;
            const link = document.createElement("a");
            link.className = "candidate-link";
            link.href = `${city.id}/${candidate.id}/`;
            link.innerHTML = `
              <div class="candidate-name">${candidate.name}</div>
              <div class="candidate-meta">${candidate.party || "無黨籍/未標註"} · ${candidate.postCount} 則貼文 · 最新 ${formatDate(candidate.latestPostAt)}</div>
            `;
            card.appendChild(link);
          });
          grid.appendChild(card);
        });
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
        datasets: [{ data: values }],
      },
      options: { plugins: { legend: { position: "bottom" } } },
    });
  }

  function renderCandidate() {
    const candidateId = body.dataset.candidateId;
    Promise.all([fetchJson(`api/posts/${candidateId}.json`), fetchJson("api/spectrum.json")])
      .then(([postsPayload, spectrumPayload]) => {
        const candidate = postsPayload.candidate;
        document.getElementById("candidate-name").textContent = `${candidate.name}（${candidate.cityLabel}）`;
        document.getElementById("candidate-party").textContent = candidate.party || "無黨籍/未標註";

        const linksEl = document.getElementById("candidate-links");
        Object.entries(candidate.links || {}).forEach(([platform, url]) => {
          if (!url) return;
          const a = document.createElement("a");
          a.href = url;
          a.target = "_blank";
          a.rel = "noopener";
          a.textContent = platform;
          linksEl.appendChild(a);
        });

        const spectrumEntry = spectrumPayload.candidates.find((c) => c.candidateId === candidateId);
        renderTopicChart(document.getElementById("topic-chart"), spectrumEntry ? spectrumEntry.topicProportions : {});

        const list = document.getElementById("post-list");
        list.innerHTML = "";
        if (!postsPayload.posts.length) {
          list.innerHTML = '<li class="empty-state">尚無抓取到的貼文。</li>';
          return;
        }
        postsPayload.posts.forEach((post) => {
          const li = document.createElement("li");
          li.className = "post-item";
          const topics = (post.topics || []).map((t) => `<span>${t}</span>`).join("");
          li.innerHTML = `
            <div class="post-platform">${post.platform}</div>
            <div>${(post.text || "").replace(/\n/g, "<br>")}</div>
            <div class="post-topics">${topics}</div>
            <div class="candidate-meta">${formatDate(post.postedAt)} · <a href="${post.url}" target="_blank" rel="noopener">原始連結</a></div>
          `;
          list.appendChild(li);
        });
      })
      .catch((err) => {
        document.getElementById("post-list").textContent = `資料載入失敗：${err.message}`;
      });
  }

  if (body.dataset.page === "index") {
    renderIndex();
  } else if (body.dataset.page === "candidate") {
    renderCandidate();
  }
})();
