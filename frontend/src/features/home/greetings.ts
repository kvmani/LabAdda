/**
 * Dynamic, personalized greeting generator for LabAdda.
 * Provides over 150 warm, collegiate greetings tailored by time of day,
 * lab research curiosity, and friendly peer encouragement.
 */

export function formatSalutationName(displayName?: string): string {
  if (!displayName || !displayName.trim()) return "colleague";
  const parts = displayName.trim().split(/\s+/);
  if (
    parts.length >= 2 &&
    (parts[0] === "Dr." || parts[0] === "Prof." || parts[0] === "Shri" || parts[0] === "Smt.")
  ) {
    return `${parts[0]} ${parts[1]}`;
  }
  return parts[0] || "colleague";
}

// Morning Greetings (5:00 AM - 11:59 AM) - 40 variations
const MORNING_TEMPLATES: ((name: string) => string)[] = [
  (n) => `Good morning, ${n}! Fresh coffee, fresh ideas ready for the lab?`,
  (n) => `Rise and shine, ${n}! Ready to explore something new today?`,
  (n) => `Good morning, ${n}! What hypothesis are we testing today?`,
  (n) => `A bright morning to you, ${n}. May your samples behave and your data align!`,
  (n) => `Morning, ${n}! What's the first question on your bench today?`,
  (n) => `Good morning, ${n}! A new day of curious thinking awaits.`,
  (n) => `Hey ${n}, early morning lab inspiration strikes first!`,
  (n) => `Good morning, ${n}! Ready to turn yesterday's notes into today's breakthroughs?`,
  (n) => `Wishing you a productive morning, ${n}!`,
  (n) => `Morning, ${n}! The whiteboard is clean and ready for your sketches.`,
  (n) => `Good morning, ${n}! Got that spark of an idea this morning?`,
  (n) => `Hello ${n}, wishing you clear results and steady calibrations today!`,
  (n) => `Good morning, ${n}! What exciting problem shall we untangle first?`,
  (n) => `A crisp morning to you, ${n}! Great science begins with a curious glance.`,
  (n) => `Morning, ${n}! Hope your morning tea is strong and your day is bright.`,
  (n) => `Good morning, ${n}! Have you jotted down your morning thoughts in My Notes?`,
  (n) => `Hey ${n}, good morning! Your team spaces are buzzing and ready for you.`,
  (n) => `Good morning, ${n}! Another opportunity to learn something unexpected.`,
  (n) => `Morning, ${n}! Check your calendar—let's make today count!`,
  (n) => `Good morning, ${n}! Ready to push the boundaries of knowledge today?`,
  (n) => `A warm morning welcome, ${n}! What's on top of your priority list?`,
  (n) => `Good morning, ${n}! Every great discovery started on a morning just like this.`,
  (n) => `Morning, ${n}! Let's turn curiosity into progress today.`,
  (n) => `Good morning, ${n}! May your morning runs give crisp, reproducible spectra!`,
  (n) => `Hey ${n}, good morning! Time to sync up with colleagues and share findings.`,
  (n) => `Good morning, ${n}! What are we building or testing today?`,
  (n) => `Morning, ${n}! The lab noticeboard is updated and waiting for you.`,
  (n) => `Good morning, ${n}! An open mind and a sharp pencil can conquer any puzzle.`,
  (n) => `A very good morning, ${n}! Ready for some high-impact teamwork?`,
  (n) => `Morning, ${n}! Let's make today's experiments both safe and insightful.`,
  (n) => `Good morning, ${n}! Don't forget to take a breather between observations.`,
  (n) => `Hey ${n}, good morning! Ready to collaborate and solve challenges together?`,
  (n) => `Good morning, ${n}! What new perspective are you bringing to the table today?`,
  (n) => `Morning, ${n}! Fresh start, clear head, exciting questions.`,
  (n) => `Good morning, ${n}! Hope your day is filled with pleasant eureka moments!`,
  (n) => `A cheerful morning to you, ${n}! Let's turn data into understanding.`,
  (n) => `Good morning, ${n}! Teamwork turns complex problems into manageable steps.`,
  (n) => `Morning, ${n}! Grab your notepad and let's dive right in.`,
  (n) => `Good morning, ${n}! Wishing you smooth runs and inspiring discussions today.`,
  (n) => `Hey ${n}, top of the morning to you! Let's get things moving.`,
];

// Afternoon Greetings (12:00 PM - 4:59 PM) - 35 variations
const AFTERNOON_TEMPLATES: ((name: string) => string)[] = [
  (n) => `Good afternoon, ${n}! How are the day's experiments shaping up?`,
  (n) => `Hope your afternoon is going smoothly, ${n}! Any interesting findings so far?`,
  (n) => `Afternoon check-in, ${n}! Taking a moment to sketch out the next steps?`,
  (n) => `Good afternoon, ${n}! How are the observations looking today?`,
  (n) => `Hey ${n}, hope your afternoon is productive and your focus is sharp!`,
  (n) => `Good afternoon, ${n}! Time for a quick progress review with the team?`,
  (n) => `Afternoon, ${n}! The second half of the day holds the best breakthroughs.`,
  (n) => `Good afternoon, ${n}! Remember to stay hydrated between lab bench trials.`,
  (n) => `Hello ${n}, hope your afternoon discussions are sparking creative insights!`,
  (n) => `Good afternoon, ${n}! Ready to log your midday milestones in Tasks?`,
  (n) => `Hey ${n}, how's the data looking this afternoon? Spotting any trends?`,
  (n) => `Good afternoon, ${n}! A quick chat with a colleague can unlock tricky bottlenecks.`,
  (n) => `Afternoon, ${n}! Ready to draw out that mechanism on the whiteboard?`,
  (n) => `Good afternoon, ${n}! Halfway through the day—keep the momentum going!`,
  (n) => `Hey ${n}, good afternoon! Hope your synthesis runs are yielding pure results.`,
  (n) => `Good afternoon, ${n}! What's the main goal for the remainder of the day?`,
  (n) => `Afternoon, ${n}! Take a moment to capture any sudden inspiration in My Notes.`,
  (n) => `Good afternoon, ${n}! Ready to share an update on the noticeboard?`,
  (n) => `Hey ${n}, hope you had a great lunch! Ready for an impactful afternoon?`,
  (n) => `Good afternoon, ${n}! Patience and persistence always solve the toughest riddles.`,
  (n) => `Afternoon, ${n}! Let's turn raw observations into actionable conclusions.`,
  (n) => `Good afternoon, ${n}! Any surprising curves or data points today?`,
  (n) => `Hey ${n}, wishing you a calm and steady afternoon of work.`,
  (n) => `Good afternoon, ${n}! Team coordination is just a chat message away.`,
  (n) => `Afternoon, ${n}! What's the next test parameter on your checklist?`,
  (n) => `Good afternoon, ${n}! Keep pushing forward; great findings take careful steps.`,
  (n) => `Hey ${n}, good afternoon! A quick sticky note can save a great idea.`,
  (n) => `Good afternoon, ${n}! How is Project Tejas / lab collaboration coming along?`,
  (n) => `Afternoon, ${n}! Keep your team in the loop with a brief check-in.`,
  (n) => `Good afternoon, ${n}! Take pride in the small steps you've accomplished today.`,
  (n) => `Hey ${n}, hope your afternoon calibrations are spot on!`,
  (n) => `Good afternoon, ${n}! Let's make these hours count toward your next milestone.`,
  (n) => `Afternoon, ${n}! What does the whiteboard say about our next phase?`,
  (n) => `Good afternoon, ${n}! Inspiring ideas often arrive midway through the task.`,
  (n) => `Hey ${n}, good afternoon! Ready to wrap up another successful set of tests?`,
];

// Evening Greetings (5:00 PM - 9:59 PM) - 35 variations
const EVENING_TEMPLATES: ((name: string) => string)[] = [
  (n) => `Good evening, ${n}! Wrapping up findings or starting a late sketch?`,
  (n) => `Evening, ${n}! How did the results turn out today?`,
  (n) => `Good evening, ${n}! Time to log today's wins and plan tomorrow's steps.`,
  (n) => `Hey ${n}, winding down? Don't forget to jot down any stray thoughts in My Notes!`,
  (n) => `Good evening, ${n}! A day of diligent lab work well done.`,
  (n) => `Evening, ${n}! Great job keeping the team connected today.`,
  (n) => `Good evening, ${n}! Taking a quiet moment to reflect on today's progress?`,
  (n) => `Hey ${n}, good evening! Reviewing your tasks before heading out?`,
  (n) => `Good evening, ${n}! Even negative results teach us which path to explore next.`,
  (n) => `Evening, ${n}! Let's celebrate the small victories of today's work.`,
  (n) => `Good evening, ${n}! Ready to organize your whiteboard for tomorrow's review?`,
  (n) => `Hey ${n}, hope you had a fruitful day at the institute!`,
  (n) => `Good evening, ${n}! The evening quiet is perfect for deep contemplation.`,
  (n) => `Evening, ${n}! Any final notices to share with the division before you pack up?`,
  (n) => `Good evening, ${n}! Rest and relaxation are key ingredients for fresh thinking.`,
  (n) => `Hey ${n}, good evening! Time to check off those completed action items.`,
  (n) => `Good evening, ${n}! Thank you for your dedication to the lab's mission.`,
  (n) => `Evening, ${n}! Tomorrow brings a brand new set of possibilities.`,
  (n) => `Good evening, ${n}! Hope your day's work brought you closer to your goals.`,
  (n) => `Hey ${n}, good evening! Reviewing the group chat for any late updates?`,
  (n) => `Good evening, ${n}! A tidy workspace and clear notes make tomorrow a breeze.`,
  (n) => `Evening, ${n}! What was the most intriguing thing you learned today?`,
  (n) => `Good evening, ${n}! Leave yourself a note so you can pick right back up.`,
  (n) => `Hey ${n}, good evening! Great colleagues make tough research challenges rewarding.`,
  (n) => `Good evening, ${n}! Science is a marathon; celebrate every step forward.`,
  (n) => `Evening, ${n}! Take a moment to appreciate how much ground was covered today.`,
  (n) => `Good evening, ${n}! Any upcoming deadlines to mark on your Calendar?`,
  (n) => `Hey ${n}, good evening! Relax your mind and recharge for another bright day.`,
  (n) => `Good evening, ${n}! Signing off soon? LabAdda will keep your boards safe.`,
  (n) => `Evening, ${n}! Peaceful evenings often bring the most creative clarity.`,
  (n) => `Good evening, ${n}! What's the key takeaway from today's experiments?`,
  (n) => `Hey ${n}, good evening! Wishing you a peaceful evening with family and friends.`,
  (n) => `Good evening, ${n}! Ready to leave the bench and recharge?`,
  (n) => `Evening, ${n}! Another productive chapter added to the lab notebook.`,
  (n) => `Good evening, ${n}! You've put in a solid day of work. Well done!`,
];

// Late Night Greetings (10:00 PM - 4:59 AM) - 20 variations
const NIGHT_TEMPLATES: ((name: string) => string)[] = [
  (n) => `Burning the midnight oil, ${n}? Great discoveries often happen in quiet hours!`,
  (n) => `Late night lab inspiration strikes, ${n}? We've got your whiteboard ready.`,
  (n) => `Working late, ${n}? Remember to take a break and rest well tonight.`,
  (n) => `Hey ${n}, quiet night for deep focus. What are you unraveling?`,
  (n) => `Late night check-in, ${n}! Don't forget that rest is vital for sharp science.`,
  (n) => `Hello ${n}, burning the late-night lamp? Make sure to save your thoughts in Notes.`,
  (n) => `Working through the night, ${n}? Keep up the passion, but get some sleep soon!`,
  (n) => `Hey ${n}, nocturnal brainstorming mode on? Let your ideas flow freely.`,
  (n) => `Late night hours, ${n}! The whole institute is quiet—just you and your ideas.`,
  (n) => `Working past midnight, ${n}? A cup of warm water and a clear mind work wonders.`,
  (n) => `Hey ${n}, late night analysis session? Hope the data trends are crystallizing!`,
  (n) => `The late hour brings calm clarity, ${n}. Just remember to get adequate rest!`,
  (n) => `Midnight inspiration, ${n}? Capture it quickly before you call it a day!`,
  (n) => `Still exploring, ${n}? True scientific curiosity knows no clock!`,
  (n) => `Quiet night, ${n}. Jot down your thoughts and get ready for a fresh tomorrow.`,
  (n) => `Working late on a critical milestone, ${n}? We are cheering for you!`,
  (n) => `Hey ${n}, the lab never sleeps when there are questions to be answered!`,
  (n) => `Late night brainstorming, ${n}? Let the whiteboard hold your overnight thoughts.`,
  (n) => `Burning the midnight oil, ${n}? Take care and get some good rest soon!`,
  (n) => `Night owl mode activated, ${n}! What mystery are we decoding tonight?`,
];

// Anytime / Research & Collaboration Themed Greetings - 50 variations
const GENERAL_TEMPLATES: ((name: string) => string)[] = [
  (n) => `Hey ${n}, what's up today? Any new experiments or ideas?`,
  (n) => `Welcome back, ${n}! What exciting puzzle are we solving today?`,
  (n) => `Hey ${n}, ready to sketch something new on the whiteboard?`,
  (n) => `Every great breakthrough started with a simple sketch, ${n}. What's on your mind?`,
  (n) => `Welcome, ${n}! Collaboration makes good science great. Ready to team up?`,
  (n) => `Hey ${n}, your ideas matter. Let's make them visible on LabAdda!`,
  (n) => `Hello ${n}! What new questions are driving your curiosity today?`,
  (n) => `Hey ${n}, remember: small daily discoveries add up to monumental shifts.`,
  (n) => `Welcome back, ${n}! Let's make today an inspiring day for your team.`,
  (n) => `Hey ${n}, got a quick question for a teammate? The chat is right here!`,
  (n) => `Hello ${n}! Great to see you. How can LabAdda assist your lab work today?`,
  (n) => `Hey ${n}, every note you save brings you one step closer to clarity.`,
  (n) => `Welcome, ${n}! Science thrives when colleagues share ideas openly.`,
  (n) => `Hey ${n}, have you shared your latest research milestone with your division?`,
  (n) => `Hello ${n}! Your personal workbench and team boards are ready.`,
  (n) => `Hey ${n}, what is nature teaching us in the laboratory today?`,
  (n) => `Welcome back, ${n}! A supportive community turns complex science into joy.`,
  (n) => `Hey ${n}, ready to organize your day and check off some goals?`,
  (n) => `Hello ${n}! Let's turn discussions into clear, actionable tasks.`,
  (n) => `Hey ${n}, what new angle shall we look at that problem from today?`,
  (n) => `Welcome, ${n}! When in doubt, sketch it out on My Whiteboard!`,
  (n) => `Hey ${n}, great insights often come from the most informal chats.`,
  (n) => `Hello ${n}! Keep asking bold questions—that is where real progress begins.`,
  (n) => `Hey ${n}, what's on your scientific radar today?`,
  (n) => `Welcome back, ${n}! Your collaborative workspace is primed and ready.`,
  (n) => `Hey ${n}, let's build something durable and impactful together today.`,
  (n) => `Hello ${n}! Curiosity is contagious—share an interesting thought today.`,
  (n) => `Hey ${n}, how are your project timelines looking? Take a peek at Calendar!`,
  (n) => `Welcome, ${n}! A clean notebook and an open mind can solve anything.`,
  (n) => `Hey ${n}, ready to explore new experimental horizons today?`,
  (n) => `Hello ${n}! Every observation has a story. What is your data telling you?`,
  (n) => `Hey ${n}, collaboration is the fastest bridge from concept to reality.`,
  (n) => `Welcome back, ${n}! Let's make today's efforts count toward excellence.`,
  (n) => `Hey ${n}, got a hunch or an intuition? Draft it in your private notes first!`,
  (n) => `Hello ${n}! Teamwork divides the effort and multiplies the effect.`,
  (n) => `Hey ${n}, what's the most exciting challenge on your plate right now?`,
  (n) => `Welcome, ${n}! We are glad you are here. Let's make today remarkable.`,
  (n) => `Hey ${n}, keep your team aligned with a quick noticeboard post.`,
  (n) => `Hello ${n}! In research, every small measurement is a brick in the temple of knowledge.`,
  (n) => `Hey ${n}, got sticky notes for your brainstorming session? Open My Whiteboard!`,
  (n) => `Welcome back, ${n}! What new knowledge will we uncover together today?`,
  (n) => `Hey ${n}, stay curious, stay collaborative, and have a wonderful session!`,
  (n) => `Hello ${n}! Progress happens one thoughtful experiment at a time.`,
  (n) => `Hey ${n}, great to see you on LabAdda. What's the main focus today?`,
  (n) => `Welcome, ${n}! Simple tools empower the deepest scientific work.`,
  (n) => `Hey ${n}, share an encouraging word with a colleague in chat today!`,
  (n) => `Hello ${n}! From molecular structures to project roadmaps, let's sketch it out.`,
  (n) => `Hey ${n}, ready to dive into today's lab challenges with a smile?`,
  (n) => `Welcome back, ${n}! Together, our research teams achieve the extraordinary.`,
  (n) => `Hey ${n}, what new frontiers are we exploring in the lab today?`,
];

/**
 * Total combined template count: 40 + 35 + 35 + 20 + 50 = 180 rich variations!
 *
 * Chooses a greeting dynamically based on time of day and a rotating seed,
 * guaranteeing both temporal relevance and continuous variety across visits.
 */
export function getDynamicGreeting(displayName?: string, date: Date = new Date()): string {
  const name = formatSalutationName(displayName);
  const hour = date.getHours();

  let pool: ((n: string) => string)[];
  if (hour >= 5 && hour < 12) {
    // 65% morning-specific, 35% general
    pool = [...MORNING_TEMPLATES, ...GENERAL_TEMPLATES.slice(0, 20)];
  } else if (hour >= 12 && hour < 17) {
    // 65% afternoon-specific, 35% general
    pool = [...AFTERNOON_TEMPLATES, ...GENERAL_TEMPLATES.slice(15, 35)];
  } else if (hour >= 17 && hour < 22) {
    // 65% evening-specific, 35% general
    pool = [...EVENING_TEMPLATES, ...GENERAL_TEMPLATES.slice(30, 50)];
  } else {
    // Late night
    pool = [...NIGHT_TEMPLATES, ...GENERAL_TEMPLATES.slice(0, 15)];
  }

  // Pick pseudo-randomly using timestamp and sessionStorage rotation if available
  let index = 0;
  try {
    const lastStr = sessionStorage.getItem("labadda_greeting_seed");
    const last = lastStr ? parseInt(lastStr, 10) : Math.floor(Math.random() * pool.length);
    index = (last + 1) % pool.length;
    sessionStorage.setItem("labadda_greeting_seed", index.toString());
  } catch {
    index = Math.floor(Math.random() * pool.length);
  }

  const template = pool[index] ?? pool[0] ?? ((n: string) => `Welcome, ${n}!`);
  return template(name);
}
