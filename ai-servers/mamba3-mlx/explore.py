import mlx.core as mx
import mlx.nn as nn
import math

class MLXMamba3Block(nn.Module):
    """
    Prototype de bloc Mamba-3 adapté pour MLX.
    
    Inspiré de l'article "Mamba-3: Improved Sequence Modeling using State Space Principles" (arXiv:2603.15569).
    
    Mamba-3 introduit :
      1. Discrétisation exponentielle-trapézoïdale.
      2. Mises à jour d'état à valeurs complexes (Complex-Valued State Update).
      3. Formulation Multi-Input, Multi-Output (MIMO).
    """
    def __init__(
        self,
        d_model: int,
        d_state: int = 32,      # Mamba-3 utilise 2x moins d'état que Mamba-2 pour une perplexité équivalente
        d_inner: int = None,
        dt_rank: int = None,
        mimo_groups: int = 4    # Nombre de groupes MIMO
    ):
        super().__init__()
        self.d_model = d_model
        self.d_state = d_state
        self.d_inner = d_inner or 2 * d_model
        self.dt_rank = dt_rank or math.ceil(self.d_model / 16)
        self.mimo_groups = mimo_groups

        # Projections d'entrée (linéaires + convolutions)
        self.in_proj = nn.Linear(d_model, self.d_inner * 2, bias=False)
        self.conv1d = nn.Conv1d(
            in_channels=self.d_inner,
            out_channels=self.d_inner,
            kernel_size=4,
            padding=3
        )

        # Projections de paramètres SSM (Delta, B, C)
        self.x_proj = nn.Linear(self.d_inner, self.dt_rank + 2 * self.d_state, bias=False)
        self.dt_proj = nn.Linear(self.dt_rank, self.d_inner, bias=True)

        # Mamba-3 : Paramètres A à valeurs complexes (représentés par deux tenseurs réels pour MLX)
        # A_real et A_imag sont de forme (d_inner, d_state)
        # Initialisés de manière appropriée pour assurer la stabilité du SSM complexe
        self.A_real = mx.array(mx.random.uniform(-1.0, 0.0, [self.d_inner, self.d_state]))
        self.A_imag = mx.array(mx.random.uniform(-math.pi, math.pi, [self.d_inner, self.d_state]))

        # Projection de sortie
        self.out_proj = nn.Linear(self.d_inner, d_model, bias=False)

    def discretize_trapezoidal(self, u_real, u_imag, delta, A_real, A_imag):
        """
        Implémente la discrétisation Exponentielle-Trapézoïdale de Mamba-3.
        Contrairement à Euler/Exponentiel classique (Mamba-1/Mamba-2), elle prend en compte
        les contributions aux deux extrémités de l'intervalle.
        
        dx/dt = A x + B u
        Approximation trapézoïdale sur l'intervalle [t, t+delta] :
        x(t+delta) ≈ (I - (delta/2)*A)^(-1) [ (I + (delta/2)*A) x(t) + delta * B * u_mid ]
        
        Note : Cette implémentation séquentielle sert de référence pour le prototypage. 
        Dans le code de production MLX, cela est optimisé via le kernel Metal fusionné (fused Mamba-3 SSD kernel).
        """
        # Représentation de l'opération en nombres complexes sur MLX (en utilisant la partie réelle et imaginaire)
        # delta a pour forme (B, L, D)
        # A a pour forme (D, N)
        
        # Pour des raisons de performance, nous simulons la récurrence complexe :
        # A_discrete = exp(delta * A)
        # Mais dans Mamba-3, la forme trapézoïdale modifie le coefficient de transmission.
        
        # Calcul de A_discrete complexe (exp(delta * A))
        delta_A_real = mx.expand_dims(delta, -1) * self.A_real       # (B, L, D, N)
        delta_A_imag = mx.expand_dims(delta, -1) * self.A_imag       # (B, L, D, N)
        
        # Norme exponentielle complexe
        exp_real = mx.exp(delta_A_real)
        cos_imag = mx.cos(delta_A_imag)
        sin_imag = mx.sin(delta_A_imag)
        
        A_discrete_real = exp_real * cos_imag
        A_discrete_imag = exp_real * sin_imag
        
        # Coefficient trapézoïdal multiplicateur pour le signal d'entrée B * u
        # B_discrete = (I - (delta/2)*A)^(-1) * delta * B
        # Approximation :
        denom_real = 1.0 - 0.5 * delta_A_real
        denom_imag = -0.5 * delta_A_imag
        denom_sq = denom_real**2 + denom_imag**2
        
        # Inverse complexe
        inv_real = denom_real / denom_sq
        inv_imag = -denom_imag / denom_sq
        
        return A_discrete_real, A_discrete_imag, inv_real, inv_imag

    def __call__(self, x: mx.array) -> mx.array:
        # Forme d'entrée : (B, L, D) - Batch, Longueur séquence, Dimension modèle
        batch, seq_len, _ = x.shape

        # 1. Projection d'entrée et Split
        xz = self.in_proj(x)
        x_split, z = mx.split(xz, 2, axis=-1)

        # 2. Convolution 1D locale sur les canaux
        # MLX attend (B, L, C) pour Conv1D si configuré par défaut
        x_conv = self.conv1d(x_split)
        x_conv = x_conv[:, :seq_len, :] # Tronquer à la longueur d'origine suite au padding
        x_active = x_conv * mx.sigmoid(x_conv) # SiLU

        # 3. Projection des paramètres SSM
        # x_proj produit les représentations de Delta, B (complexe), C (complexe)
        ssm_params = self.x_proj(x_active)
        
        # Séparation de Delta (dt), B et C
        dt, B_proj, C_proj = mx.split(
            ssm_params, 
            [self.dt_rank, self.dt_rank + self.d_state], 
            axis=-1
        )
        
        delta = mx.logaddexp(self.dt_proj(dt), mx.array(0.0)) # Softplus

        # 4. MIMO et Discrétisation Exponentielle-Trapézoïdale
        # Mamba-3 applique les calculs complexes sur les états.
        # Ici nous simulons la récurrence de l'état h_t avec l'approximation trapézoïdale.
        
        # Initialisation de l'état caché (complexe) : (B, d_inner, d_state)
        h_real = mx.zeros((batch, self.d_inner, self.d_state))
        h_imag = mx.zeros((batch, self.d_inner, self.d_state))
        
        # Mamba-3 MIMO : projection d'entrée multiplexée (B, L, d_inner, d_state)
        # B et C agissent comme des vecteurs complexes pour l'écriture/lecture de la mémoire
        B_real = B_proj # Pour simplifier, nous projetons en réel
        B_imag = mx.zeros_like(B_proj) # Partie imaginaire à 0 à l'entrée
        
        output_list = []
        
        # Calcul de la récurrence (simulée pas-à-pas pour la démonstration)
        # Note : Dans le kernel Metal officiel (#3519), ceci est entièrement parallélisé (Scan associatif)
        A_discrete_real, A_discrete_imag, inv_real, inv_imag = self.discretize_trapezoidal(
            x_active, mx.zeros_like(x_active), delta, self.A_real, self.A_imag
        )

        for t in range(seq_len):
            u_t = x_active[:, t, :, None] # (B, d_inner, 1)
            b_r_t = B_real[:, t, None, :] # (B, 1, d_state)
            
            # Entrée complexe
            inp_real = u_t * b_r_t # (B, d_inner, d_state)
            
            # Application de la discrétisation trapézoïdale sur l'état
            # h(t) = A_d * h(t-1) + B_d * u(t)
            # Produit complexe A_d * h(t-1)
            ah_r = A_discrete_real[:, t] * h_real - A_discrete_imag[:, t] * h_imag
            ah_i = A_discrete_real[:, t] * h_real + A_discrete_imag[:, t] * h_imag
            
            # Produit complexe inv * inp_real (B_discrete * u)
            in_r = inv_real[:, t] * inp_real
            in_i = inv_imag[:, t] * inp_real
            
            # Mise à jour
            h_real = ah_r + in_r
            h_imag = ah_i + in_i
            
            # Lecture de l'état par C (complexe)
            c_r_t = C_proj[:, t, None, :] # (B, 1, d_state)
            
            # Sortie y = Re(h * C^H)
            y_t = mx.sum(h_real * c_r_t, axis=-1) # (B, d_inner)
            output_list.append(y_t)
            
        y = mx.stack(output_list, axis=1) # (B, L, d_inner)

        # Multiplier par la porte z (Gating)
        y = y * (z * mx.sigmoid(z)) # SiLU(z)

        # 5. Projection finale de sortie
        return self.out_proj(y)

if __name__ == "__main__":
    print("Test d'instanciation de MLXMamba3Block...")
    # Simulation d'un batch de 2 séquences de longueur 64, d_model = 128
    x_input = mx.random.normal([2, 64, 128])
    
    mamba3 = MLXMamba3Block(d_model=128, d_state=32)
    output = mamba3(x_input)
    
    print("Forme d'entrée :", x_input.shape)
    print("Forme de sortie :", output.shape)
    print("Instanciation et propagation avant réussies !")
