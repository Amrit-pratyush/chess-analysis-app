import io
import math
import os
import shutil
from collections import Counter
from flask import Flask, render_template, request, jsonify
import chess
import chess.engine
import chess.pgn
import chess.svg
import chess.polyglot

app = Flask(__name__)

BOOK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Performance.bin")

def get_engine_path(user_custom_path=None):
    if user_custom_path:
        cleaned_path = user_custom_path.strip().strip('"').strip("'")
        if cleaned_path and os.path.isfile(cleaned_path):
            return cleaned_path

    for linux_path in ["/usr/games/stockfish", "/usr/bin/stockfish", "/usr/local/bin/stockfish"]:
        if os.path.isfile(linux_path):
            return linux_path

    system_engine = shutil.which("stockfish") or shutil.which("stockfish.exe")
    if system_engine:
        return system_engine

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "stockfish-windows-x86-64-avx2", "stockfish", "stockfish-windows-x86-64-avx2.exe"),
        os.path.join(base_dir, "stockfish-windows-x86-64-avx2", "stockfish-windows-x86-64-avx2.exe"),
        os.path.join(base_dir, "stockfish", "stockfish-windows-x86-64-avx2.exe"),
        os.path.join(base_dir, "stockfish.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path

    return "stockfish"

def check_is_book(reader, board_before: chess.Board, move: chess.Move, ply: int) -> bool:
    if ply > 26 or not reader:
        return False
    try:
        entries = list(reader.find_all(board_before))
        book_moves = [entry.move for entry in entries]
        return move in book_moves
    except Exception:
        return False

def score_to_white_win_pct(pov_score: chess.engine.PovScore) -> float:
    try:
        white_score = pov_score.white()
        if white_score.is_mate():
            mate_in = white_score.mate()
            if mate_in is not None:
                return 100.0 if mate_in > 0 else 0.0
            return 50.0

        cp = white_score.score()
        if cp is None:
            return 50.0

        return 100.0 / (1.0 + math.exp(-0.0055 * cp))
    except Exception:
        return 50.0

def format_eval_label(pov_score: chess.engine.PovScore) -> str:
    try:
        white_score = pov_score.white()
        if white_score.is_mate():
            mate = white_score.mate()
            return f"M{mate}" if mate and mate > 0 else f"-M{abs(mate)}" if mate else "M"
        cp = white_score.score()
        if cp is None:
            return "0.0"
        return f"{cp / 100:+.1f}" if cp != 0 else "0.0"
    except Exception:
        return "0.0"

def calculate_move_accuracy(win_loss: float, label: str) -> float:
    if label in ["Book", "Best", "Brilliant (!!)", "Great (!)"]:
        return 100.0
    if win_loss <= 0.05:
        return 100.0
    
    acc = 100.0 * math.exp(-0.075 * pow(win_loss, 1.12))
    return max(0.0, min(100.0, acc))

def calculate_overall_accuracy(move_accuracies: list) -> float:
    if not move_accuracies:
        return 0.0
    return round(sum(move_accuracies) / len(move_accuracies), 1)

def estimate_rating(accuracy: float) -> int:
    if accuracy >= 95:
        return int(2400 + (accuracy - 95) * 80)
    elif accuracy >= 90:
        return int(2000 + (accuracy - 90) * 80)
    elif accuracy >= 80:
        return int(1500 + (accuracy - 80) * 50)
    elif accuracy >= 70:
        return int(1000 + (accuracy - 70) * 50)
    elif accuracy >= 50:
        return int(500 + (accuracy - 50) * 25)
    return 400

def is_piece_hanging_or_sacrificed(board_before: chess.Board, move: chess.Move, turn: chess.Color) -> bool:
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
    moved_piece = board_before.piece_at(move.from_square)
    
    if not moved_piece or moved_piece.piece_type == chess.PAWN:
        return False

    mover_val = piece_values.get(moved_piece.piece_type, 0)
    target_piece = board_before.piece_at(move.to_square)
    cap_val = piece_values.get(target_piece.piece_type, 0) if target_piece else 0

    temp_board = board_before.copy()
    temp_board.push(move)
    enemy_color = not turn

    attackers = list(temp_board.attackers(enemy_color, move.to_square))
    defenders = list(temp_board.attackers(turn, move.to_square))

    if (mover_val - cap_val) >= 2 and len(attackers) > 0:
        return True

    if not attackers:
        return False

    if moved_piece.piece_type == chess.QUEEN:
        if len(defenders) == 0:
            return True
        for att_sq in attackers:
            att_piece = temp_board.piece_at(att_sq)
            if att_piece and piece_values.get(att_piece.piece_type, 1) <= 3:
                return True
        return False

    if len(defenders) == 0:
        return True
    
    for att_sq in attackers:
        att_piece = temp_board.piece_at(att_sq)
        if att_piece and piece_values.get(att_piece.piece_type, 1) < mover_val:
            return True

    return False

def classify_move_multipv(board_before: chess.Board, move: chess.Move, best_move: chess.Move, 
                          win_before_white: float, win_after_white: float, turn: chess.Color, 
                          is_book: bool, pov_score: chess.engine.PovScore = None,
                          prev_opponent_loss: float = 0.0, line2_win_gap: float = 0.0) -> str:
    
    # 0. Book Move Check
    if is_book:
        return "Book"

    # 1. Immediate Checkmate Guard
    temp_board = board_before.copy()
    temp_board.push(move)
    if temp_board.is_checkmate():
        return "Best"

    win_before_mover = win_before_white if turn == chess.WHITE else (100.0 - win_before_white)
    win_after_mover = win_after_white if turn == chess.WHITE else (100.0 - win_after_white)
    win_loss = max(0.0, win_before_mover - win_after_mover)

    # 2. Critical Blunder Guard (Prioritize Blunder over Miss on decisive drops/mates)
    if win_loss >= 20.0 or (win_after_mover <= 5.0 and win_before_mover >= 40.0):
        return "Blunder (??)"

    # 3. Forced Mate Target
    is_mate_eval = False
    if pov_score:
        score_mover = pov_score.white() if turn == chess.WHITE else pov_score.black()
        if score_mover.is_mate() and score_mover.mate() and score_mover.mate() > 0:
            is_mate_eval = True

    # 4. Brilliant Move (Strict: Must be Best Move + Sound Sacrifice + Maintain Winning Position)
    is_sac = is_piece_hanging_or_sacrificed(board_before, move, turn)
    moved_piece = board_before.piece_at(move.from_square)

    if move == best_move and is_sac:
        # Prevent false-positive brilliant moves on unsound/refutable sacs
        if win_loss <= 0.05 and win_after_mover >= 52.0:
            if is_mate_eval or win_before_mover <= 80.0:
                return "Brilliant (!!)"

    # 5. Great Move (Single winning/finding move with significant drop on alternatives)
    if move == best_move and line2_win_gap >= 7.0 and win_loss <= 0.05 and win_before_mover <= 70.0:
        return "Great (!)"

    # 6. Best Move Guard
    if move == best_move or win_loss <= 0.2:
        return "Best"

    # 7. Miss Classification
    if prev_opponent_loss >= 10.0 and win_loss >= 10.0:
        return "Miss"
    if win_before_mover >= 75.0 and win_loss >= 15.0:
        return "Miss"

    # 8. Evaluation Drop Brackets
    if win_before_mover >= 96.0 and win_after_mover >= 90.0:
        if win_loss <= 4.0:
            return "Good"
        return "Inaccuracy (?!)"

    if win_loss >= 10.0:
        return "Mistake (?)"
    elif win_loss >= 4.0:
        return "Inaccuracy (?!)"
    elif win_loss >= 1.8:
        return "Good"
    
    return "Excellent"

def get_arrow_color(label: str) -> str:
    if "Brilliant" in label:
        return "#10b981cc"
    if "Great" in label:
        return "#38bdf8cc"
    if "Book" in label:
        return "#d97706cc"
    if "Best" in label or "Excellent" in label:
        return "#059669cc"
    if "Good" in label:
        return "#3b82f6cc"
    if "Inaccuracy" in label:
        return "#f59e0bcc"
    if "Mistake" in label:
        return "#f97316cc"
    if "Miss" in label:
        return "#ea580ccc"
    return "#dc2626cc"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.json or {}
    pgn_text = data.get("pgn", "").strip()

    try:
        depth = int(data.get("depth", 10))
        depth = max(8, min(14, depth))
    except (ValueError, TypeError):
        depth = 10

    if not pgn_text:
        return jsonify({"error": "No PGN provided."}), 400

    stockfish_path = get_engine_path(data.get("stockfish_path"))

    try:
        pgn = io.StringIO(pgn_text)
        game = chess.pgn.read_game(pgn)
        if not game:
            return jsonify({"error": "Invalid PGN format."}), 400

        board = game.board()
        white_player = game.headers.get("White", "White")
        black_player = game.headers.get("Black", "Black")

        moves_payload = []
        white_accuracies, black_accuracies = [], []
        white_counts, black_counts = Counter(), Counter()

        initial_svg = chess.svg.board(board=board, size=400)
        engine_limit = chess.engine.Limit(depth=depth)

        is_game_in_book = True
        book_reader = None
        if os.path.exists(BOOK_PATH):
            try:
                book_reader = chess.polyglot.open_reader(BOOK_PATH)
            except Exception:
                book_reader = None

        last_move_win_loss = 0.0

        with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
            engine.configure({"Threads": 1, "Hash": 16})
            mainline_moves = list(game.mainline_moves())

            current_analysis_multi = engine.analyse(board, engine_limit, multipv=2)
            current_analysis = current_analysis_multi[0]

            for idx, move in enumerate(mainline_moves):
                ply = idx + 1
                turn = board.turn
                player = "White" if turn == chess.WHITE else "Black"

                best_move = current_analysis.get("pv", [move])[0]
                best_move_san = board.san(best_move)
                win_before_white = score_to_white_win_pct(current_analysis["score"])

                line2_win_gap = 0.0
                if len(current_analysis_multi) > 1:
                    line2_white = score_to_white_win_pct(current_analysis_multi[1]["score"])
                    line1_mover = win_before_white if turn == chess.WHITE else (100.0 - win_before_white)
                    line2_mover = line2_white if turn == chess.WHITE else (100.0 - line2_white)
                    line2_win_gap = max(0.0, line1_mover - line2_mover)

                if is_game_in_book and check_is_book(book_reader, board, move, ply):
                    move_is_book = True
                else:
                    move_is_book = False
                    is_game_in_book = False

                san_notation = board.san(move)
                board_before = board.copy()
                board.push(move)

                if board.is_checkmate():
                    win_after_white = 100.0 if turn == chess.WHITE else 0.0
                    eval_str = "#"
                    next_analysis_multi = [{"score": chess.engine.PovScore(chess.engine.Mate(0), chess.WHITE), "pv": [move]}]
                    next_analysis = next_analysis_multi[0]
                    win_loss = 0.0
                    label = "Best"
                else:
                    next_analysis_multi = engine.analyse(board, engine_limit, multipv=2)
                    next_analysis = next_analysis_multi[0]
                    win_after_white = score_to_white_win_pct(next_analysis["score"])
                    eval_str = format_eval_label(next_analysis["score"])

                    win_loss = (win_before_white - win_after_white) if turn == chess.WHITE else (win_after_white - win_before_white)
                    win_loss = max(0.0, win_loss)

                    label = classify_move_multipv(
                        board_before, move, best_move, win_before_white, win_after_white, turn, 
                        move_is_book, next_analysis["score"], prev_opponent_loss=last_move_win_loss,
                        line2_win_gap=line2_win_gap
                    )

                last_move_win_loss = win_loss
                move_acc = calculate_move_accuracy(win_loss, label)

                if turn == chess.WHITE:
                    white_accuracies.append(move_acc)
                    white_counts[label] += 1
                else:
                    black_accuracies.append(move_acc)
                    black_counts[label] += 1

                arrows = [chess.svg.Arrow(move.from_square, move.to_square, color=get_arrow_color(label))]
                if move != best_move and label not in ["Best", "Brilliant (!!)", "Book", "Great (!)"]:
                    arrows.append(chess.svg.Arrow(best_move.from_square, best_move.to_square, color="#10b98177"))

                svg_board = chess.svg.board(board=board, lastmove=move, arrows=arrows, size=400)

                moves_payload.append({
                    "ply": ply,
                    "move_num": (idx // 2) + 1,
                    "turn": player,
                    "san": san_notation,
                    "best_san": best_move_san,
                    "label": label,
                    "win_loss": round(win_loss, 1),
                    "eval_white": round(win_after_white, 1),
                    "eval_str": eval_str,
                    "svg": svg_board
                })

                current_analysis_multi = next_analysis_multi
                current_analysis = next_analysis

        if book_reader:
            book_reader.close()

        w_avg = calculate_overall_accuracy(white_accuracies)
        b_avg = calculate_overall_accuracy(black_accuracies)

        categories = [
            "Brilliant (!!)",
            "Great (!)",
            "Best",
            "Excellent",
            "Good",
            "Book",
            "Inaccuracy (?!)",
            "Mistake (?)",
            "Miss",
            "Blunder (??)"
        ]

        return jsonify({
            "white_player": white_player,
            "black_player": black_player,
            "white_accuracy": w_avg,
            "black_accuracy": b_avg,
            "white_rating": estimate_rating(w_avg),
            "black_rating": estimate_rating(b_avg),
            "categories_order": categories,
            "white_counts": {cat: white_counts.get(cat, 0) for cat in categories},
            "black_counts": {cat: black_counts.get(cat, 0) for cat in categories},
            "initial_svg": initial_svg,
            "moves": moves_payload
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)