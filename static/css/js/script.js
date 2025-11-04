// === Doughnut Chart ===
const ctx1 = document.getElementById('statusChart');
if (ctx1) {
  new Chart(ctx1, {
    type: 'doughnut',
    data: {
      labels: ['เสร็จแล้ว', 'กำลังทำ', 'รอดำเนินการ'],
      datasets: [{
        data: [doneCount, inProgressCount, pendingCount],
        backgroundColor: ['#28a745', '#ffc107', '#dc3545'],
      }]
    },
    options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
  });
}

// === Trend Line Chart ===
const ctx2 = document.getElementById('trendChart');
if (ctx2) {
  new Chart(ctx2, {
    type: 'line',
    data: {
      labels: trendLabels,
      datasets: [{
        label: 'จำนวนงานต่อวัน',
        data: trendData,
        fill: true,
        borderColor: '#1c5cbbff',
        tension: 0.3,
        backgroundColor: 'rgba(13,110,253,0.1)'
      }]
    },
    options: { responsive: true, plugins: { legend: { display: false } } }
  });
}
