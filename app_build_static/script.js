document.addEventListener('DOMContentLoaded', () => {
    try {
        const data = resultsData; // From results.js
        
        // 1. Setup Filter Dropdown
        const filterSelect = document.getElementById('regionFilter');
        const regions = Object.keys(data.region_payment);
        regions.forEach(region => {
            const option = document.createElement('option');
            option.value = region;
            option.textContent = region;
            filterSelect.appendChild(option);
        });
        
        // 2. Render Region Payment Chart
        const regionCtx = document.getElementById('regionChart').getContext('2d');
        const initialPayments = Object.values(data.region_payment);
        
        let regionChart = new Chart(regionCtx, {
            type: 'bar',
            data: {
                labels: regions,
                datasets: [{
                    label: '평균 월지급금 (천원)',
                    data: initialPayments,
                    backgroundColor: 'rgba(79, 172, 254, 0.7)',
                    borderColor: 'rgba(0, 242, 254, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#1a1a1a' } } },
                scales: {
                    y: { beginAtZero: true, ticks: { color: '#2d3748' }, grid: { color: 'rgba(0, 0, 0, 0.1)' } },
                    x: { ticks: { color: '#2d3748' }, grid: { display: false } }
                }
            }
        });

        // 3. Filter Interactivity
        filterSelect.addEventListener('change', (e) => {
            const selectedRegion = e.target.value;
            if (selectedRegion === 'all') {
                regionChart.data.labels = regions;
                regionChart.data.datasets[0].data = initialPayments;
            } else {
                regionChart.data.labels = [selectedRegion];
                regionChart.data.datasets[0].data = [data.region_payment[selectedRegion]];
            }
            regionChart.update();
        });

        // 4. Render VOC Chart
        const vocCtx = document.getElementById('vocChart').getContext('2d');
        new Chart(vocCtx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(data.voc_summary),
                datasets: [{
                    data: Object.values(data.voc_summary),
                    backgroundColor: [
                        'rgba(46, 204, 113, 0.7)', // 칭찬
                        'rgba(52, 152, 219, 0.7)', // 질의
                        'rgba(231, 76, 60, 0.7)',  // 불만
                        'rgba(241, 196, 15, 0.7)'  // 요청
                    ],
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'right', labels: { color: '#1a1a1a' } } }
            }
        });

        // 5. Render Keyword Chart (Stacked Horizontal Bar by VOC Category)
        const keywordCtx = document.getElementById('keywordChart').getContext('2d');
        const catData = data.voc_category_keywords;
        
        new Chart(keywordCtx, {
            type: 'bar',
            data: {
                labels: catData.labels,
                datasets: [
                    {
                        label: '질의',
                        data: catData.datasets['질의'],
                        backgroundColor: 'rgba(52, 152, 219, 0.7)'
                    },
                    {
                        label: '요청',
                        data: catData.datasets['요청'],
                        backgroundColor: 'rgba(241, 196, 15, 0.7)'
                    },
                    {
                        label: '불만',
                        data: catData.datasets['불만'],
                        backgroundColor: 'rgba(231, 76, 60, 0.7)'
                    },
                    {
                        label: '칭찬',
                        data: catData.datasets['칭찬'],
                        backgroundColor: 'rgba(46, 204, 113, 0.7)'
                    }
                ]
            },
            options: {
                indexAxis: 'y', // horizontal bar chart
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: true, position: 'bottom', labels: { color: '#1a1a1a' } }, 
                    title: { display: true, text: '유형별 키워드 분석 (교차 분석)', color: '#1a1a1a', font: {size: 14} } 
                },
                scales: {
                    x: { stacked: true, beginAtZero: true, ticks: { color: '#2d3748' }, grid: { color: 'rgba(0, 0, 0, 0.1)' } },
                    y: { stacked: true, ticks: { color: '#2d3748' }, grid: { display: false } }
                }
            }
        });

        // 3. Render Time Series Chart (with Prediction)
        const tsCtx = document.getElementById('tsChart').getContext('2d');
        const tsData = data.time_series_trend;
        new Chart(tsCtx, {
            type: 'line',
            data: {
                labels: tsData.labels,
                datasets: [
                    {
                        label: '실제 가입건수',
                        data: tsData.actual,
                        borderColor: 'rgba(46, 204, 113, 1)',
                        backgroundColor: 'rgba(46, 204, 113, 0.2)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: '예측 가입건수 (시계열 모델링)',
                        data: tsData.predicted,
                        borderColor: 'rgba(241, 196, 15, 1)',
                        backgroundColor: 'rgba(241, 196, 15, 0.1)',
                        borderDash: [5, 5],
                        fill: true,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#1a1a1a' } } },
                scales: {
                    y: { beginAtZero: true, ticks: { color: '#2d3748' }, grid: { color: 'rgba(0, 0, 0, 0.1)' } },
                    x: { ticks: { color: '#2d3748' }, grid: { display: false } }
                }
            }
        });

    } catch (error) {
        console.error('Error loading static data:', error);
    }
});
