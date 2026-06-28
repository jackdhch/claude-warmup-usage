import SwiftUI

func levelColor(_ p: Int) -> Color {
    if p >= 80 { return .red }
    if p >= 50 { return .orange }
    return .green
}

struct UsageBar: View {
    let label: String
    let pct: Int
    let prominent: Bool

    var body: some View {
        HStack(spacing: 8) {
            Text(label)
                .font(.system(size: prominent ? 13 : 12))
                .foregroundStyle(prominent ? Color.primary : Color.secondary)
                .frame(width: 22, alignment: .leading)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.white.opacity(0.16))
                    Capsule()
                        .fill(prominent ? levelColor(pct) : Color.gray.opacity(0.55))
                        .frame(width: geo.size.width * CGFloat(min(max(pct, 0), 100)) / 100)
                }
            }
            .frame(height: prominent ? 12 : 6)
            Text("\(pct)%")
                .font(.system(size: prominent ? 19 : 13, weight: prominent ? .semibold : .regular))
                .foregroundStyle(prominent ? Color.primary : Color.secondary)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                .fixedSize(horizontal: true, vertical: false)
                .frame(width: 46, alignment: .trailing)
        }
    }
}

// Shared card: Claude mark + relative refresh time, then the two bars.
// (Hosts add their own refresh button at the top-right.)
struct UsageCard: View {
    let data: UsageData

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 5) {
                Image(systemName: "sparkles")
                    .font(.system(size: 13))
                    .foregroundStyle(Color(red: 0.85, green: 0.47, blue: 0.34))
                Text(data.relativeUpdated)
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                Spacer(minLength: 0)
            }
            UsageBar(label: "5h", pct: data.fiveUsed, prominent: true)
            UsageBar(label: "周", pct: data.weekUsed, prominent: false)
        }
        .padding(12)
    }
}
