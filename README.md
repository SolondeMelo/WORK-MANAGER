**Work Manager - INSTRUÇÕES**
================================

1) **REQUISITOS**
   - Python 3 instalado no seu computador (Windows, Mac ou Linux).
   - No Linux, se der erro de "tkinter" faltando, rode:
         sudo apt install python3-tk

2) *(RECOMENDADO)* Instalar o Pillow para poder usar sua foto de perfil:
         pip install Pillow
   Sem o Pillow o programa funciona normalmente, só não mostra a foto.

3) **COMO RODAR**
   Abra o terminal/prompt de comando na pasta onde está o arquivo
   "MAIN.py" e digite:
         python3 MAIN.py
   (no Windows pode ser apenas "python MAIN.py")

4) **SEUS DADOS**
   Tudo que você cadastrar fica salvo automaticamente em um arquivo
   chamado "dados_freelancer.db", criado do lado do script. Não apague
   esse arquivo ou você perderá o histórico. Para fazer backup, basta
   copiar esse arquivo para outro lugar.

5) **COMO USAR**
   - Clique no lápis ao lado do nome no topo do menu para renomear
     seu espaço (a aba com nome editável).
   - Em "Diárias", defina o valor padrão que você ganha por dia.
   - Em "Trabalhos", clique em "+ Novo Trabalho" e dê um nome a ele.
     Isso cria uma nova aba clicável na lateral, com esse nome.
   - Dentro do trabalho, clique em "+ Adicionar Dia Trabalhado", escolha
     a data no mini calendário (sem digitar nada) e confirme o valor
     recebido naquele dia (já vem preenchido com sua diária padrão, mas
     pode alterar se ganhou mais ou menos naquele dia específico).
   - O valor total a receber daquele trabalho é atualizado automaticamente.
   - Quando receber o pagamento combinado, clique em " Finalizar Trampo".
     O trabalho sai da lista de "em andamento" e vai para a aba
     "Trabalhos Finalizados", onde você também pode clicar em
     "Ver histórico" para consultar todos os dias e valores daquele
     trabalho no futuro.
   - No topo do menu, o "Dashboard" (nome editável) mostra o total já
     recebido e o total ainda a receber dos trabalhos em andamento.
