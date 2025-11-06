from abc import ABC, abstractmethod

# -------------------------------------------------------------------
# 1. CLASES BASE Y ENTIDADES (Herencia y Polimorfismo)
# -------------------------------------------------------------------

class CuentaBase(ABC):
    """Clase Padre Abstracta. Define el contrato contable."""
    def __init__(self, codigo, nombre, saldo_inicial):
        self.codigo = codigo
        self.nombre = nombre
        # Convención de encapsulamiento (el saldo es 'protegido')
        self._saldo = saldo_inicial

    def get_saldo(self):
        return self._saldo

    @abstractmethod
    def debitar(self, monto):
        """Método abstracto que debe ser implementado por las hijas."""
        pass

    @abstractmethod
    def acreditar(self, monto):
        """Método abstracto que debe ser implementado por las hijas."""
        pass

    def __str__(self):
        """Método mágico para imprimir el objeto."""
        return f"- {self.codigo} | {self.nombre:<20} | Tipo: {self.__class__.__name__:<15} | Saldo: {self._saldo:,.2f}"

# Activo: Naturaleza Deudora (Débito suma)
class CuentaActivo(CuentaBase):
    def debitar(self, monto):
        self._saldo += monto
    def acreditar(self, monto):
        self._saldo -= monto

# Pasivo: Naturaleza Acreedora (Crédito suma)
class CuentaPasivo(CuentaBase):
    def debitar(self, monto):
        self._saldo -= monto
    def acreditar(self, monto):
        self._saldo += monto

# -------------------------------------------------------------------
# 2. CLASE DE VALIDACIÓN (Asiento)
# -------------------------------------------------------------------

class Movimiento:
    def __init__(self, cuenta, debe, haber):
        self.cuenta = cuenta
        self.debe = debe
        self.haber = haber
    
    @classmethod
    def crear_debito(cls, cuenta, monto):
        return cls(cuenta, monto, 0)
    
    @classmethod
    def crear_credito(cls, cuenta, monto):
        return cls(cuenta, 0, monto)


class Asiento:
    def __init__(self, concepto):
        self.concepto = concepto
        self.movimientos = []

    def agregar_debito(self, cuenta, monto):
        self.movimientos.append(Movimiento.crear_debito(cuenta, monto))

    def agregar_credito(self, cuenta, monto):
        self.movimientos.append(Movimiento.crear_credito(cuenta, monto))

    def confirmar(self):
        total_debe = sum(m.debe for m in self.movimientos)
        total_haber = sum(m.haber for m in self.movimientos)

        # Cláusula de Guarda (Partida Doble)
        if total_debe != total_haber:
            print(f"\t❌ Error Partida Doble: Debe ({total_debe:,.2f}) != Haber ({total_haber:,.2f}). Cancelado.")
            return False
        
        # Aplicar movimientos (Polimorfismo en acción)
        for mov in self.movimientos:
            if mov.debe > 0:
                mov.cuenta.debitar(mov.debe)
            elif mov.haber > 0:
                mov.cuenta.acreditar(mov.haber)
        
        print(f"\t✅ Asiento '{self.concepto}' confirmado. Total: {total_debe:,.2f}.")
        return True


# -------------------------------------------------------------------
# 3. PROGRAMA PRINCIPAL (Uso)
# -------------------------------------------------------------------

def ejecutar_ejemplo():
    # Setup
    caja = CuentaActivo("1.1.01", "Caja", 10000.00)
    proveedores = CuentaPasivo("2.1.01", "Proveedores", 15000.00)
    
    print("--- Saldos Iniciales ---")
    print(caja)
    print(proveedores)

    # Operación: Pago a Proveedores $2000
    asiento_pago = Asiento("Pago a Proveedores")
    # Activo (Caja) disminuye (Acreditar)
    asiento_pago.agregar_credito(caja, 2000.00)
    # Pasivo (Proveedores) disminuye (Debitar)
    asiento_pago.agregar_debito(proveedores, 2000.00)

    asiento_pago.confirmar()

    print("\n--- Saldos Finales ---")
    print(caja)
    print(proveedores)

ejecutar_ejemplo()