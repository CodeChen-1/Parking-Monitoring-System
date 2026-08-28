function showToast(message) {
  const toastElement = document.getElementById('plateToast');
  const toastBody = document.getElementById('toastMessage');
  toastBody.innerText = "Detected plate: " + message;
  const toast = new bootstrap.Toast(toastElement);
  toast.show();
}

function pollNotifications() {
  fetch('/get_notifications')
    .then(response => response.json())
    .then(data => {
      data.forEach(item => {
        showToast(item.plate);
      });
    })
    .catch(error => console.error("Notification fetch error:", error));
}

setInterval(pollNotifications, 3000);

function showChart(chartName) {
  const containers = ['weekly', 'monthly', 'yearly'];
  containers.forEach(name => {
    const container = document.getElementById(`${name}Container`);
    container.style.display = (name === chartName) ? 'block' : 'none';
  });
}

function updateCarCount() {
  fetch('/current-count')
    .then(res => res.json())
    .then(data => {
      const counterElement = document.getElementById('carCount');
      if (counterElement) {
        counterElement.textContent = data.count;
      }
    })
    .catch(err => console.error("Error fetching car count:", err));
}

// 👇 Combined DOMContentLoaded event
document.addEventListener("DOMContentLoaded", () => {
  const path = window.location.pathname;

  if (path === "/analysis") {
    fetch('/analysis-data')
      .then(res => res.json())
      .then(data => {
        console.log(data);
        createChart('weeklyChart', 'Car Entries', data.weekly);
        createChart('monthlyChart', 'Car Entries', data.monthly);
        createChart('yearlyChart', 'Car Entries', data.yearly);
      });

    function createChart(canvasId, label, rawData) {
      let labels = [];
      let dataMap = new Map();
      let counts = [];

      const now = new Date();

      if (canvasId === 'weeklyChart') {
        labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        rawData.forEach(([dayLabel, count]) => {
          dataMap.set(dayLabel, count);
        });
        counts = labels.map(label => dataMap.get(label) || 0);

      } else if (canvasId === 'monthlyChart') {
        const year = now.getFullYear();
        const month = now.getMonth();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        labels = Array.from({ length: daysInMonth }, (_, i) => (i + 1).toString());

        rawData.forEach(([label, count]) => {
          const day = parseInt(label.split(' ')[1], 10).toString(); // e.g., "Jun 03" -> "3"
          dataMap.set(day, count);
        });
        counts = labels.map(label => dataMap.get(label) || 0);

        const currentMonthLabel = now.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        const monthlyLabel = document.getElementById('monthlyLabel');
        if (monthlyLabel) monthlyLabel.textContent = currentMonthLabel;

      } else if (canvasId === 'yearlyChart') {
        labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

        rawData.forEach(([monthLabel, count]) => {
          dataMap.set(monthLabel, count);
        });
        counts = labels.map(label => dataMap.get(label) || 0);

        const currentYearLabel = "Year: " + now.getFullYear();
        const yearlyLabel = document.getElementById('yearlyLabel');
        if (yearlyLabel) yearlyLabel.textContent = currentYearLabel;
      }

      new Chart(document.getElementById(canvasId), {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: label,
            data: counts,
            backgroundColor: 'rgba(54, 162, 235, 0.6)'
          }]
        },
        options: {
          responsive: true,
          scales: {
            y: {
              beginAtZero: true,
              ticks: { stepSize: 1 },
              suggestedMax: 10
            }
          }
        }
      });
    }

  } else if (path === "/live") {
    updateCarCount(); 
    setInterval(updateCarCount, 3000);
  }
});
