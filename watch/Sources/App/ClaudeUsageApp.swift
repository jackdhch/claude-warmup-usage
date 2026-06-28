import SwiftUI

@main
struct ClaudeUsageApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

// Full-colour app screen: the card plus a working refresh button.
struct ContentView: View {
    @State private var data = UsageData.placeholder
    @State private var loading = false

    var body: some View {
        ZStack(alignment: .topTrailing) {
            UsageCard(data: data)
                .background(Color(white: 0.11), in: RoundedRectangle(cornerRadius: 18))

            Button {
                Task { await refresh() }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 15))
                    .rotationEffect(.degrees(loading ? 360 : 0))
                    .animation(loading ? .linear(duration: 0.8).repeatForever(autoreverses: false)
                                       : .default, value: loading)
            }
            .buttonStyle(.plain)
            .padding(10)
        }
        .task { await refresh() }
    }

    func refresh() async {
        loading = true
        if let d = await fetchUsage() { data = d }
        loading = false
    }
}
