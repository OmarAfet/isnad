import type { Metadata } from "next";
import { SiteFooter, SiteHeader } from "@/components/isnad/site-shell";

export const metadata: Metadata = { title: "كيف يشتغل إسناد" };

// The specialist page. Technical detail lives here and nowhere else, and every number on it was
// measured by a script in the repository that prints the command that produced it.

const STATS = [
  { n: "40,389", label: "نص موثق" },
  { n: "9", label: "لغات للبحث" },
  { n: "99.8%", label: "من الأحاديث لها حكم منقول" },
  { n: "29/29", label: "تطابق مع الدرر السنية" },
];

export default function Method() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-2xl flex-1 px-5 pt-16 pb-4">
        <h1 className="text-4xl font-bold leading-tight">كيف يشتغل إسناد</h1>
        <p className="mt-4 text-lg text-muted-foreground">
          يختار النص من مصادر موثقة، وما يكتب نص من عنده.
        </p>

        <dl className="mt-10 grid grid-cols-2 gap-x-6 gap-y-8 border-y py-8 sm:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label}>
              <dt className="sr-only">{s.label}</dt>
              <dd className="text-3xl font-bold tabular-nums">
                <bdi>{s.n}</bdi>
              </dd>
              <dd className="mt-1 text-sm text-muted-foreground">{s.label}</dd>
            </div>
          ))}
        </dl>

        <Section title="مرحلتين: بحث ثم قرار">
          <p>
            <b>البحث.</b> يدوّر في كل النصوص بطريقتين مع بعض: بالمعنى عن طريق نموذج تضمين متعدد
            اللغات (multilingual-e5-base)، وباللفظ عن طريق BM25. المعنى يلقى الوصف اللي ما يشارك
            النص ولا كلمة، واللفظ يلقى العبارة اللي تذكرها صح. الطريقتين مع بعض جابت ضعف دقة كل وحدة
            لحالها.
          </p>
          <p>
            <b>القرار.</b> أقرب 120 نص تروح لنموذج Jev من TypeSafe. في الدور الأول يختار من كل 12
            نص أقربها لوصفك. وفي الدور الثاني يختار من الفائزين نص واحد، ويعطي نسبة تطابقه مع وصفك.
          </p>
          <p>
            في كل دور فيه خيار إنه ما فيه نص مطابق، وإذا اختاره يقول لك إسناد إنه ما لقى.
          </p>
          <p>
            الحديث الواحد يتكرر في أكثر من كتاب، فإسناد يجمع النسخ المتشابهة في نتيجة وحدة ويعرض
            باقيها تحت {"\"ورد أيضًا في\""}. بدون هذا كانت النسخ تتقاسم النسبة بينها، وتطلع الثقة أقل كل ما
            كثرت نسخ النص الصحيح.
          </p>
        </Section>

        <Section title="من وين يجيب النصوص">
          <ul className="list-disc space-y-2 ps-5">
            <li>القرآن الكريم بالرسم العثماني من مجمع الملك فهد، والبحث يكون بالرسم الإملائي.</li>
            <li>صحيح البخاري وصحيح مسلم والسنن الأربع: 34,153 حديث.</li>
            <li>
              أحكام الأحاديث منقولة بأسماء العلماء، مثل الألباني وشعيب الأرناؤوط وأحمد شاكر. إسناد ما
              يحكم على حديث من عنده.
            </li>
            <li>
              الترجمات المنشورة بثماني لغات تُستخدم للوصول للنص فقط، والنتيجة دايم هي النص العربي
              مع اسم المترجم.
            </li>
          </ul>
        </Section>

        <Section title="وش ما يسويه">
          <ul className="list-disc space-y-2 ps-5">
            <li>ما يكتب نص، ولا يترجم نص شرعي من عنده.</li>
            <li>ما يحكم على صحة حديث، ينقل حكم العلماء بأسمائهم.</li>
            <li>ما يفتي. إذا كان سؤالك يحتاج فتوى، يوجهك لأهل العلم.</li>
            <li>
              يبحث في القرآن والكتب الستة بس. الحديث اللي برّاها يطلع لك {"\"ما لقينا\""}، مو نص قريب منه.
            </li>
          </ul>
        </Section>

        <Section title="كيف تتحقق بنفسك">
          <p>
            كل نتيجة فيها المصدر ورقم الحديث، وزر يفتح نفس النص في الدرر السنية. قارنّا أحكامنا
            بأحكام الدرر السنية على عينة عشوائية. الأحاديث اللي قدرنا نطابقها بالكتاب والرقم كانت 29
            من 29 متفقة في الدرجة.
          </p>
        </Section>
      </main>
      <SiteFooter />
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-12">
      <h2 className="mb-4 text-2xl font-bold">{title}</h2>
      <div className="space-y-4 leading-loose">{children}</div>
    </section>
  );
}
