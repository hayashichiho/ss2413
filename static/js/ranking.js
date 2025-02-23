// ゲーム終了処理とランキング表示を統合
async function endGameAndShowRanking() {
    try {
        // 最終スコアを送信
        await fetch('/api/update_distance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                player_id: playerId,
                distance: distance * 0.04,
                is_final: true
            }),
        });

        // ゲーム終了を通知
        await fetch('/api/end_game', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ player_id: playerId }), // プレイヤーIDを送信
        });

        // ランキングを取得して表示
        window.location.href = '/ranking';

    } catch (error) {
        console.error('Error in endGameAndShowRanking:', error);
    }
}

// 距離と順位を更新する関数
async function updateDistanceAndRank(playerId, distance) {
    if (tmr % 15 !== 0) return; // 15フレームに1回のみ更新

    try {
        // 距離を更新
        await fetch('/api/update_distance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ player_id: playerId, distance: distance * 0.04 }),
        });

        // 全プレイヤーの距離情報を取得
        const playersResponse = await fetch('/api/players');
        if (!playersResponse.ok) {
            throw new Error('Players fetch failed');
        }

        const players = await playersResponse.json();
        // 距離でソート（降順）
        playerDistances = players.sort((a, b) => b.distance - a.distance);

        // 現在の順位と総プレイヤー数を更新
        currentRank = playerDistances.findIndex(p => p.player_id === playerId) + 1;
        totalPlayers = playerDistances.length;

    } catch (error) {
        console.error('Error updating distance and rank:', error);
    }
}

function showDistanceMap() {
    const MAP_HEIGHT = 300;  // マップの高さを300pxに拡大
    const MAP_WIDTH = 40;    // マップの幅を40pxに拡大
    const MARKER_SIZE = 10;  // マーカーサイズを10pxに拡大
    const X_POSITION = 20;   // X座標の開始位置は維持

    // 背景の黒い矩形を描画
    fRect(X_POSITION - 5, 80, MAP_WIDTH + 10, MAP_HEIGHT + 10, "black");

    // プレイヤーが存在する場合のみ描画
    if (playerDistances.length > 0) {
        // 最大距離と最小距離を取得
        const maxDistance = Math.max(...playerDistances.map(p => p.distance));
        const minDistance = Math.min(...playerDistances.map(p => p.distance));
        const distanceRange = maxDistance - minDistance;

        // 各プレイヤーの位置を描画
        playerDistances.forEach((player, index) => {
            // Y座標を計算（距離に応じて位置を決定）
            const normalizedDistance = (player.distance - minDistance) / distanceRange;
            const y = 85 + (MAP_HEIGHT - 10) * (1 - normalizedDistance);

            if (player.player_id === playerId) {
                // 自分の位置を赤い三角で表示
                const triangleHeight = 20;  // 三角形の高さを20pxに拡大
                const triangleWidth = 16;   // 三角形の幅を16pxに拡大
                fTri(
                    X_POSITION + MAP_WIDTH / 2, y - triangleHeight / 2,  // 頂点
                    X_POSITION + MAP_WIDTH / 2 - triangleWidth / 2, y + triangleHeight / 2,  // 左下
                    X_POSITION + MAP_WIDTH / 2 + triangleWidth / 2, y + triangleHeight / 2,  // 右下
                    "red"
                );
            } else {
                // 他プレイヤーを白い円で表示
                bg.beginPath();
                bg.fillStyle = "white";
                bg.arc(X_POSITION + MAP_WIDTH / 2, y, MARKER_SIZE / 2, 0, Math.PI * 2);
                bg.fill();
            }
        });
    }
}

// 順位を表示する関数
function showRankingDisplay() {
    // 背景の黒い矩形を描画
    fRect(20, 20, 120, 60, "black");

    // 順位テキストを描画
    const rankText = `${currentRank}/${totalPlayers}`;
    fText(rankText, 80, 50, 50, "white");
}

function showRanking() {
    // まずDOM要素の存在確認
    const rankingContainer = document.getElementById('ranking-container');
    if (!rankingContainer) {
        console.error('Ranking container not found!');
        return;
    }

    fetch('/api/ranking')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Ranking:", data);
            if (!data || data.length === 0) {
                rankingContainer.innerHTML = '<h2>ランキング</h2><p>データがありません</p>';
                return;
            }

            rankingContainer.innerHTML = '<h2>ランキング</h2>';
            const rankingList = document.createElement('ul');
            data.forEach(player => {
                const listItem = document.createElement('li');
                listItem.textContent = `${player.name}: ${player.distance}m`;
                rankingList.appendChild(listItem);
            });
            rankingContainer.appendChild(rankingList);
        })
        .catch(error => {
            console.error('Error fetching ranking:', error);
            rankingContainer.innerHTML = '<h2>ランキング</h2><p>ランキングの取得に失敗しました</p>';
        });
}
