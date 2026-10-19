import sys
import subprocess

if __name__ == '__main__':
    print("Iniciando o Filtro de Dados...")
    print("O seu navegador deve abrir automaticamente em alguns segundos.")
    # Executa o Streamlit usando o executável do Python atual para evitar erros de PATH
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])
    except KeyboardInterrupt:
        print("\nAplicativo encerrado pelo usuário.")