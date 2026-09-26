(function () {
  'use strict';
  const data = JSON.parse(document.getElementById('sales-data').textContent);
  const chart = new Chart(document.getElementById('sales-chart'), {
    type: 'line',
    data: {labels: data.labels, datasets: [{label: 'ยอดอนุมัติ (บาท)', data: data.amounts, backgroundColor: 'rgba(60,141,188,.28)', borderColor: '#3c8dbc', borderWidth: 2, pointRadius: 2, lineTension: 0, fill: true}]},
    options: {responsive: true, maintainAspectRatio: false, legend: {display: false}, scales: {yAxes: [{ticks: {beginAtZero: true}}]}}
  });
  ['area', 'bar'].forEach(function (name) {
    document.getElementById(name + '-chart').addEventListener('click', function () {
      chart.config.type = name === 'area' ? 'line' : 'bar';
      chart.update();
      ['area', 'bar'].forEach(function (key) {
        const button = document.getElementById(key + '-chart');
        button.classList.toggle('btn-primary', name === key);
        button.classList.toggle('btn-outline-primary', name !== key);
        button.setAttribute('aria-pressed', String(name === key));
      });
    });
  });
  data.labels.forEach(function (label, index) {
    const row = document.createElement('tr');
    [label, data.amounts[index].toLocaleString('th-TH', {minimumFractionDigits: 2})].forEach(function (value) {
      const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell);
    });
    document.getElementById('daily-values').appendChild(row);
  });
}());
