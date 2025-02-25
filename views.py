import threading
from datetime import datetime, timedelta

from flask import (
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from sqlalchemy.future import select

from . import app, async_session, db
from .models import Player, generate_unique_player_id

game_start_time = None  # ゲーム開始時刻
lock = threading.Lock()  # ロックオブジェクト

# 減速効果の管理用
slow_effects = {}  # player_id: (end_time, speed_multiplier)


@app.route("/api/game_times", methods=["GET"])
def get_game_times():
    if game_start_time:
        return jsonify(
            {
                "start_time": game_start_time.isoformat(),
            }
        )
    else:
        return jsonify({"status": "error", "message": "Game times not set"}), 404


@app.route("/api/current_time", methods=["GET"])
def get_current_time():
    return jsonify({"current_time": datetime.utcnow().isoformat()})


@app.route("/api/game_status", methods=["GET"])
def game_status():
    game_started = Player.query.filter_by(game_started=True).first() is not None
    return jsonify({"game_started": game_started})


@app.route("/api/ranking", methods=["GET"])
def get_ranking():
    players = Player.query.order_by(Player.distance.desc()).all()
    return jsonify(
        [
            {
                "player_id": player.player_id,
                "name": player.name,
                "distance": player.distance,
            }
            for player in players
        ]
    )


@app.route("/api/update_distance", methods=["POST"])  # 距離を更新する処理
async def update_distance():
    data = request.get_json()  # リクエストのJSONデータを取得
    player_id = data.get("player_id")  # プレイヤーIDを取得
    distance = data.get("distance")  # 距離を取得

    async with async_session() as session:  # セッションを開始
        async with session.begin():  # トランザクションを開始
            try:
                result = await session.execute(
                    select(Player).filter_by(player_id=player_id)
                )
                player = result.scalars().first()  # プレイヤーを取得
                if player:
                    player.distance = distance  # 距離を更新
                    await session.commit()  # コミット
                    return jsonify({"status": "success"}), 200  # 成功時のレスポンス
                else:
                    await session.rollback()  # ロールバック
                    return jsonify(
                        {"status": "error", "message": "Player not found"}
                    ), 404  # 失敗時のレスポンス
            except Exception as e:
                await session.rollback()  # ロールバック
                app.logger.error(
                    f"Error updating distance: {str(e)}"
                )  # エラーメッセージをログに出力
                return jsonify(
                    {"status": "error", "message": str(e)}
                ), 500  # 失敗時のレスポンス


@app.route("/api/end_game", methods=["POST"])  # ゲームを終了する処理
async def end_game():
    data = request.get_json()  # リクエストのJSONデータを取得
    player_id = data.get("player_id")  # プレイヤーIDを取得

    async with async_session() as session:  # セッションを開始
        async with session.begin():  # トランザクションを開始
            try:
                result = await session.execute(
                    select(Player).filter_by(player_id=player_id)
                )  # プレイヤーを取得
                player = result.scalars().first()  # プレイヤーを取得
                if player:
                    player.game_started = False  # ゲームを終了
                    await session.commit()  # コミット
                    return jsonify({"status": "success"}), 200  # 成功時のレスポンス
                else:
                    await session.rollback()  # ロールバック
                    return jsonify(
                        {"status": "error", "message": "Player not found"}
                    ), 404  # 失敗時のレスポンス
            except Exception as e:
                await session.rollback()  # ロールバック
                return jsonify(
                    {"status": "error", "message": str(e)}
                ), 500  # 失敗時のレスポンス


@app.route("/api/db_reset", methods=["POST"])
def db_reset():
    try:
        # データベースをリセット
        db.drop_all()
        db.create_all()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        app.logger.error(f"Error resetting database: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/game")  # ゲーム開始時の処理
def game():
    player_id = request.args.get("player_id")  # プレイヤーIDを取得
    return render_template(
        "gameBase/index.html", player_id=player_id
    )  # ゲーム画面を表示


@app.route("/ranking")  # ランキング画面を表示
def ranking():
    player_name = request.args.get("name")  # プレイヤー名を取得
    admin_name = "admin"  # 管理者の名前
    return render_template(
        "ranking.html", player_name=player_name, admin_name=admin_name
    )  # ランキング画面を表示


@app.route("/")  # ルートURLにアクセスがあった場合の処理
def index():
    return render_template("login.html")  # ログイン画面を表示


@app.route(
    "/login", methods=["POST"]
)  # ログインフォームからPOSTリクエストがあった場合の処理
def login():
    player_name = request.form["name"]  # プレイヤー名を取得
    player_id = generate_unique_player_id()  # プレイヤーIDを生成
    player = Player(
        player_id=player_id, name=player_name
    )  # プレイヤークラスのインスタンスを生成
    db.session.add(player)  # プレイヤーをデータベースに追加
    db.session.commit()  # データベースにコミット
    return redirect(
        url_for("wait", player_id=player_id, player_name=player_name)
    )  # 待機画面にリダイレクト


@app.route("/wait")  # 待機画面を表示
def wait():
    player_id = request.args.get("player_id")  # プレイヤーIDを取得
    player_name = request.args.get("player_name")  # プレイヤー名を取得
    players = [p.name for p in Player.query.all()]  # プレイヤー一覧を取得
    admin_name = "admin"  # 管理者の名前

    return render_template(
        "wait.html",  # 待機画面を表示
        player_id=player_id,
        player_name=player_name,
        players=players,
        admin_name=admin_name,
    )


@app.route("/start_game", methods=["POST"])
def start_game():
    global game_start_time
    game_start_time = datetime.utcnow() + timedelta(seconds=10)  # 10秒後にゲーム開始
    Player.query.update({Player.game_started: True})
    db.session.commit()
    return jsonify(
        {
            "status": "success",
            "start_time": game_start_time.isoformat(),
        }
    )


@app.route("/static/js/<path:filename>")  # 静的ファイルのJSを提供
def serve_js(filename):
    return send_from_directory("static/js", filename)


@app.route("/static/images/<path:filename>")  # 静的ファイルの画像を提供
def serve_images(filename):
    return send_from_directory("static/images", filename)


@app.route("/api/register", methods=["POST"])  # プレイヤーを登録
def register_player():
    data = request.get_json()
    player_id = generate_unique_player_id()
    player = Player(player_id=player_id, name=data["name"])
    db.session.add(player)
    db.session.commit()
    return jsonify(
        {
            "player_id": player.player_id,
            "name": player.name,
            "distance": player.distance,
            "game_started": player.game_started,
        }
    ), 201


@app.route("/api/players", methods=["GET"])
def get_players():
    players = Player.query.all()
    return jsonify(
        [
            {
                "player_id": player.player_id,
                "name": player.name,
                "distance": player.distance,
                "game_started": player.game_started,
            }
            for player in players
        ]
    )


@app.route("/api/apply_slow_effect", methods=["POST"])
async def apply_slow_effect():
    data = request.get_json()
    affected_players = data.get("affected_players", [])
    # デフォルト3秒(3000ミリ秒)として設定（必要に応じて変更してください）
    duration = data.get("duration", 3000)
    speed_multiplier = data.get("speed_multiplier", 0.5)

    current_time = datetime.utcnow()
    end_time = current_time + timedelta(milliseconds=duration)

    async with async_session() as session:
        try:
            for player_id in affected_players:
                result = await session.execute(
                    select(Player).filter_by(player_id=player_id)
                )
                player = result.scalars().first()
                if player:
                    # slow_effects の更新はロックで保護
                    with lock:
                        slow_effects[player_id] = (end_time, speed_multiplier)
            await session.commit()
            return jsonify({"status": "success"}), 200
        except Exception as e:
            await session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/check_effects", methods=["POST"])
async def check_effects():
    data = request.get_json()
    player_id = data.get("player_id")
    current_time = datetime.utcnow()

    # slow_effects への参照もロックで保護
    with lock:
        if player_id in slow_effects:
            end_time, speed_multiplier = slow_effects[player_id]
            if current_time < end_time:
                remaining_time = (end_time - current_time).total_seconds()
                return jsonify(
                    {
                        "is_slowed": True,
                        "speed_multiplier": speed_multiplier,
                        "remaining_time": remaining_time,
                    }
                )
            else:
                # 効果の期限が切れた場合は削除
                del slow_effects[player_id]

    return jsonify({"is_slowed": False, "speed_multiplier": 1.0})


# この関数だけを残す（GETメソッドのバージョン）
@app.route("/api/current_rank", methods=["GET"])
async def get_current_rank():
    player_id = request.args.get("player_id")

    async with async_session() as session:
        try:
            # 全プレイヤーを距離でソート
            result = await session.execute(
                select(Player).order_by(Player.distance.desc())
            )
            players = result.scalars().all()

            total_players = len(players)
            # プレイヤーの順位を特定
            current_rank = next(
                (i + 1 for i, p in enumerate(players) if p.player_id == player_id),
                total_players,
            )

            return jsonify(
                {
                    "rank": current_rank,
                    "total_players": total_players,
                    "top_players": [
                        {"id": p.player_id, "name": p.name, "distance": p.distance}
                        for p in players[:3]  # 上位3名の情報も返す
                    ],
                }
            )

        except Exception as e:
            app.logger.error(f"Error getting rank: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
