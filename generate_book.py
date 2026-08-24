import io
import chess
import chess.pgn
import chess.polyglot

# A curated master database of standard opening theory and transpositions (ECO A00 - E99)
MASTER_OPENINGS_PGN = """
[Event "Ruy Lopez: Morphy Defense"]
1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O *

[Event "Ruy Lopez: Berlin Defense"]
1. e4 e5 2. Nf3 Nc6 3. Bb5 Nf6 4. O-O Nxe4 5. d4 Nd6 6. Bxc6 dxc6 7. dxe5 Nf5 8. Qxd8+ Kxd8 *

[Event "Italian Game: Giuoco Piano"]
1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d3 d6 6. O-O a6 7. Bb3 Ba7 8. Nbd2 O-O *

[Event "Italian Game: Two Knights Defense"]
1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 Bc5 5. c3 d6 6. O-O a6 *

[Event "Scotch Game"]
1. e4 e5 2. Nf3 Nc6 3. d4 exd4 4. Nxd4 Bc5 5. Be3 Qf6 6. c3 Nge7 7. Bc4 Ne5 8. Be2 *

[Event "Four Knights Game"]
1. e4 e5 2. Nf3 Nc6 3. Nc3 Nf6 4. Bb5 Bb4 5. O-O O-O 6. d3 d6 7. Bg5 Bxc3 8. bxc3 *

[Event "Sicilian: Najdorf"]
1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be2 e5 7. Nb3 Be7 8. O-O O-O *

[Event "Sicilian: Dragon"]
1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 g6 6. Be3 Bg7 7. f3 O-O 8. Qd2 Nc6 *

[Event "Sicilian: Classical"]
1. e4 c5 2. Nf3 Nc6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 d6 6. Bg5 e6 7. Qd2 a6 8. O-O-O *

[Event "Sicilian: Scheveningen"]
1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 e6 6. Be2 Be7 7. O-O O-O 8. Be3 Nc6 *

[Event "Sicilian: French Variation / Paulsen"]
1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 a6 5. Nc3 Qc7 6. Bd3 Nf6 7. O-O Be7 *

[Event "French: Winawer"]
1. e4 e6 2. d4 d5 3. Nc3 Bb4 4. e5 c5 5. a3 Bxc3+ 6. bxc3 Ne7 7. Qg4 O-O *

[Event "Bird Opening: Nimzo-Larsen Variation"]
1. f4 d5 2. b3 Nf6 3. Bb2 c5 4. e3 g6 5. Bb5+ Bd7 6. Bxf6 exf6 7. Bxd7+ Qxd7 8. Nf3 Bg7 9. c3 f5 10. d4 b6 11. O-O O-O *

[Event "French: Classical"]
1. e4 e6 2. d4 d5 3. Nc3 Nf6 4. Bg5 Be7 5. e5 Nfd7 6. Bxe7 Qxe7 7. f4 O-O 8. Nf3 *

[Event "French: Tarrasch"]
1. e4 e6 2. d4 d5 3. Nd2 Nf6 4. e5 Nfd7 5. Bd3 c5 6. c3 Nc6 7. Ne2 cxd4 8. cxd4 *

[Event "French: Advance"]
1. e4 e6 2. d4 d5 3. e5 c5 4. c3 Nc6 5. Nf3 Qb6 6. Bd3 Bd7 7. O-O cxd4 8. cxd4 *

[Event "Caro-Kann: Classical"]
1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Bf5 5. Ng3 Bg6 6. h4 h6 7. Nf3 Nd7 8. h5 *

[Event "Caro-Kann: Advance"]
1. e4 c6 2. d4 d5 3. e5 Bf5 4. Nf3 e6 5. Be2 c5 6. Be3 Qb6 7. Nc3 Nc6 8. O-O *

[Event "Caro-Kann: Two Knights"]
1. e4 c6 2. Nc3 d5 3. Nf3 Bg4 4. h3 Bxf3 5. Qxf3 e6 6. d4 Nf6 7. Bd3 dxe4 8. Nxe4 *

[Event "Scandinavian: Mainline"]
1. e4 d5 2. exd5 Qxd5 3. Nc3 Qa5 4. d4 Nf6 5. Nf3 c6 6. Bc4 Bf5 7. Bd2 e6 8. Nd5 *

[Event "Queen's Gambit Declined: Orthodox"]
1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7 5. e3 O-O 6. Nf3 Nbd7 7. Rc1 c6 8. Bd3 *

[Event "Queen's Gambit Declined: Tartakower"]
1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7 5. e3 O-O 6. Nf3 h6 7. Bh4 b6 8. cxd5 *

[Event "Queen's Gambit Accepted"]
1. d4 d5 2. c4 dxc4 3. Nf3 Nf6 4. e3 e6 5. Bxc4 c5 6. O-O a6 7. Qe2 b5 8. Bb3 *

[Event "Slav Defense: Mainline"]
1. d4 d5 2. c4 c6 3. Nf3 Nf6 4. Nc3 dxc4 5. a4 Bf5 6. e3 e6 7. Bxc4 Bb4 8. O-O *

[Event "Semi-Slav Defense: Meran"]
1. d4 d5 2. c4 c6 3. Nf3 Nf6 4. Nc3 e6 5. e3 Nbd7 6. Bd3 dxc4 7. Bxc4 b5 8. Bd3 *

[Event "King's Indian Defense: Classical"]
1. d4 Nf6 2. c4 g6 3. Nc3 Bg7 4. e4 d6 5. Nf3 O-O 6. Be2 e5 7. O-O Nc6 8. d5 Ne7 *

[Event "Grünfeld Defense: Russian / Hungarian / Game of the Century"]
1. Nf3 Nf6 2. c4 g6 3. Nc3 Bg7 4. d4 O-O 5. Bf4 d5 6. Qb3 dxc4 7. Qxc4 c6 8. e4 Nbd7 9. Rd1 Nb6 *

[Event "Grünfeld Defense: Exchange"]
1. d4 Nf6 2. c4 g6 3. Nc3 d5 4. cxd5 Nxd5 5. e4 Nxc3 6. bxc3 Bg7 7. Bc4 c5 8. Ne2 *

[Event "Nimzo-Indian: Classical (Capablanca)"]
1. d4 Nf6 2. c4 e6 3. Nc3 Bb4 4. Qc2 O-O 5. a3 Bxc3+ 6. Qxc3 b6 7. Bg5 Bb7 *

[Event "Nimzo-Indian: Rubinstein"]
1. d4 Nf6 2. c4 e6 3. Nc3 Bb4 4. e3 O-O 5. Bd3 d5 6. Nf3 c5 7. O-O Nc6 *

[Event "London System"]
1. d4 d5 2. Bf4 Nf6 3. e3 c5 4. c3 Nc6 5. Nd2 e6 6. Ngf3 Bd6 7. Bg3 O-O *

[Event "English Opening: Symmetrical"]
1. c4 c5 2. Nc3 Nc6 3. g3 g6 4. Bg2 Bg7 5. Nf3 Nf6 6. O-O O-O 7. d4 cxd4 8. Nxd4 *

[Event "English Opening: King's English"]
1. c4 e5 2. Nc3 Nf6 3. Nf3 Nc6 4. g3 d5 5. cxd5 Nxd5 6. Bg2 Nb6 7. O-O Be7 *

[Event "Réti Opening"]
1. Nf3 d5 2. c4 c6 3. g3 Nf6 4. Bg2 Bf5 5. O-O e6 6. d3 h6 7. b3 Nbd7 *

[Event "King's Indian Attack"]
1. Nf3 Nf6 2. g3 d5 3. Bg2 c6 4. O-O Bg4 5. d3 Nbd7 6. Nbd2 e5 7. e4 Bd6 *
"""

def generate_book():
    entries = []
    pgn_io = io.StringIO(MASTER_OPENINGS_PGN.strip())
    
    while True:
        game = chess.pgn.read_game(pgn_io)
        if not game:
            break
        board = game.board()
        for move in game.mainline_moves():
            key = chess.polyglot.zobrist_hash(board)
            raw_move = chess.polyglot.encode_move(move)
            entries.append((key, raw_move, 1, 0)) # key, move, weight, learn
            board.push(move)

    # Sort entries by zobrist key ascending as required by Polyglot specification
    entries.sort(key=lambda x: x[0])

    with open("Performance.bin", "wb") as f:
        for key, move, weight, learn in entries:
            f.write(key.to_bytes(8, byteorder="big"))
            f.write(move.to_bytes(2, byteorder="big"))
            f.write(weight.to_bytes(2, byteorder="big"))
            f.write(learn.to_bytes(4, byteorder="big"))

    print(f"Successfully generated Performance.bin with {len(entries)} theoretical opening moves!")

if __name__ == "__main__":
    generate_book()