// Emoji automático cuando en los subtítulos aparece una de estas palabras.
// Añade o cambia lo que quieras: [expresión, emoji]
const REGLAS: [RegExp, string][] = [
  [/\b(dinero|pasta|millones?|d[oó]lares|pagar|rico)\b/i, "💰"],
  [/\b(polic[ií]as?|polis?|estrellas|patrulla|arrest)/i, "🚔"],
  [/\b(cocodrilos?|caim[aá]n|caimanes|lagarto)\b/i, "🐊"],
  [/\b(explot\w*|explosi[oó]n|bomba|boom|vuela)\b/i, "💥"],
  [/\b(muert[oe]s?|muere|mata\w*|matado)\b/i, "💀"],
  [/\b(coches?|carro|conduc\w*|velocidad)\b/i, "🚗"],
  [/\b(motos?)\b/i, "🏍️"],
  [/\b(avi[oó]n|avioneta|vuel[ao]|helic[oó]ptero)\b/i, "🚁"],
  [/\b(barcos?|lancha|yate)\b/i, "🛥️"],
  [/\b(playa|mar|agua|nadar)\b/i, "🏖️"],
  [/\b(fuego|quema|incendio)\b/i, "🔥"],
  [/\b(bancos?|rob\w*|atraco|golpe)\b/i, "🏦"],
  [/\b(pistola|dispar\w*|tiros?|balas?|arma)\b/i, "🔫"],
  [/\b((ja[ .,]*){2,}|(je[ .,]*){2,}|jaj\w*|risa)/i, "😂"],
  [/\b(secreto|truco|nadie sabe|escondid\w*)\b/i, "🤫"],
  [/\b(gta ?(5|v|cinco))\b/i, "5️⃣"],
  [/\b(gta ?(6|vi|seis))\b/i, "6️⃣"],
  [/\b(incre[ií]ble|brutal|locura|flipa\w*|wow|qu[eé] fuerte)\b/i, "🤯"],
  [/\b(no puede ser|qu[eé]\?|en serio)\b/i, "😳"],
];

export function emojiPara(texto: string): string | null {
  for (const [re, e] of REGLAS) if (re.test(texto)) return e;
  return null;
}
