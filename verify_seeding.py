from src.database import inicializar_banco, seed_categorias_csv, conexao

def verify_seeding():
    inicializar_banco()
    seed_categorias_csv()
    
    with conexao() as con:
        count = con.execute("SELECT COUNT(*) FROM categorias").fetchone()[0]
        print(f"Categorias no banco: {count}")
        
        sample = con.execute("SELECT grupo, nome FROM categorias LIMIT 5").fetchall()
        print("Amostra:", sample)

if __name__ == "__main__":
    verify_seeding()
