import WidgetKit
import SwiftUI
import AppIntents

struct UsageEntry: TimelineEntry {
    let date: Date
    let data: UsageData
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> UsageEntry {
        UsageEntry(date: .now, data: .placeholder)
    }

    func getSnapshot(in context: Context, completion: @escaping (UsageEntry) -> Void) {
        Task {
            let d = await fetchUsage() ?? .placeholder
            completion(UsageEntry(date: .now, data: d))
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<UsageEntry>) -> Void) {
        Task {
            let d = await fetchUsage() ?? .placeholder
            let next = Calendar.current.date(byAdding: .minute, value: 30, to: .now)
                ?? Date().addingTimeInterval(1800)
            completion(Timeline(entries: [UsageEntry(date: .now, data: d)], policy: .after(next)))
        }
    }
}

// Tapping the refresh button forces the timeline to re-fetch (watchOS 10+).
struct RefreshIntent: AppIntent {
    static var title: LocalizedStringResource = "刷新"
    func perform() async throws -> some IntentResult {
        WidgetCenter.shared.reloadAllTimelines()
        return .result()
    }
}

struct ClaudeUsageWidgetView: View {
    var entry: UsageEntry
    var body: some View {
        ZStack(alignment: .topTrailing) {
            UsageCard(data: entry.data)
            Button(intent: RefreshIntent()) {
                Image(systemName: "arrow.clockwise").font(.system(size: 13))
            }
            .buttonStyle(.plain)
            .padding(6)
        }
        .containerBackground(.black, for: .widget)
    }
}

@main
struct ClaudeUsageWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "ClaudeUsageWidget", provider: Provider()) { entry in
            ClaudeUsageWidgetView(entry: entry)
        }
        .configurationDisplayName("Claude 用量")
        .description("5 小时与每周用量")
        .supportedFamilies([.accessoryRectangular])
    }
}
