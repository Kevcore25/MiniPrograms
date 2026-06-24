VERSION = 1.0

"""
UBC Workday Schedule Matcher

It finds all possible combinations of working schedules (that *hopefully* do not conflict) with some basic filters (start/end times and minimum time gaps).

For courses that require specific discussion/labs (as of testing, like MATH_V 100) then the results may not be accurate.
I can't really fix that based on how the user input is handled right now.
"""
from datetime import datetime, timedelta
from itertools import product as itertools_product
from traceback import print_exc
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

def parse(rawText: str):
    while rawText.count('\n\n') > 0:
       rawText = rawText.replace('\n\n', '\n')

    rawTextLines = rawText.lstrip().rstrip().lstrip('\n').rstrip('\n').split('\n')

    i = 0
    result = {}

    allTypes = []

    '''
    Sample:

    CPSC_V 110-102
    Open
    Lecture

    Tue Thu | 11:00 a.m. - 12:30 p.m. | 2026-09-08 - 2026-12-03 | UBCV | HR MacMillan Building (MCML) | Floor: 3 | Room: 360 | Vsevolod Lynov

    ... (repeats)
    '''
    while i < len(rawTextLines):
        try:
            # Get basic info
            name = rawTextLines[i+0]
            status = rawTextLines[i+1].lower()
            type = rawTextLines[i+2].lower()
            rawdates = rawTextLines[i+3].split(' | ')

            # print("Found", name)

            # Parse date: Weekend | Time - Time | Date (doesn't matter in this prog) | CAMPUS (doesn't matter) | AREA (doesn't matter) | FLOOR ( doesnt matter) | ROOM (doesnt matter) | TEACHER (Doesnt matter)
            # Thus, just get: Weekend, start time, end time
            try:
                weekend = rawdates[0].split(' ')
                startTime, endTime = rawdates[1].split(' - ')
                startDate, endDate = rawdates[2].split(' - ')

                startTimeDate = datetime.strptime((startTime+startDate).replace('.', ''), '%I:%M %p%Y-%m-%d')
                endTimeDate = datetime.strptime((endTime+endDate).replace('.', ''), '%I:%M %p%Y-%m-%d')

                result[name] = {
                    "Status": status, # must be "open" 
                    "Type": type, 
                    "Weekends": weekend,
                    "Start time": startTimeDate,
                    "End time": endTimeDate
                }

                if type not in allTypes:
                    allTypes.append(type)
            except: 
                pass
            # Add 4 lines for next 
            i += 4

        except Exception as e:
            print(e)
            break

    for i in result:
        result[i]['Types'] = allTypes

    return result

def calculate(parsedDatas: list[dict[str, str|datetime]], start: str, end: str, timeBetween: int):
    '''
    parsedDatas is a list object containing a list of a dictionary that is returned by the parse function.

    start is a string that tells what the minimum start time must be in the format like: "8:00 AM" OR "8 AM"
    end is a string that tells what the maximum end time must be in the same format as start
    timeBetween is an integer that repersents the minimum time required between each course
    
    The structure looks like:

    [
        {
            name: {
                Status: status (str) - this must be "Open" to count
                Type: type (str)
                Types: all types. All of the types MUST be fulfilled (this is an assumption)
                Weekends: weekend
                Start time: the start time of the course (in a datetime obj)
                End time: the end time of the course
            }
        }
    ]
    '''
    # Parse boundary times; accept "8:00 AM", "8 AM", or "8:00" (24-hour)
    TIME_FMTS = ('%I:%M %p', '%I %p', '%H:%M', '%H')
    startTime = endTime = None
    for fmt in TIME_FMTS:
        try:
            startTime = datetime.strptime(start.strip().upper(), fmt).time()
            break
        except ValueError:
            pass
    for fmt in TIME_FMTS:
        try:
            endTime = datetime.strptime(end.strip().upper(), fmt).time()
            break
        except ValueError:
            pass
    if startTime is None or endTime is None:
        raise ValueError(f"Unrecognised time format. Use '8:00 AM', '8 AM', or '08:00'. Got: start='{start}', end='{end}'")

    gap = timedelta(minutes=timeBetween)
    base = datetime(2000, 1, 1)

    def to_dt(t):
        return base.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

    # Build all valid section combos for each course (one section per required type)
    courseOptions = []
    for courseData in parsedDatas:
        if not courseData:
            continue
        allTypes = next(iter(courseData.values()))['Types']
        if not allTypes:
            continue

        byType = {t: [] for t in allTypes}
        for name, section in courseData.items():
            if section['Status'] == 'open':
                byType[section['Type']].append((name, section))

        # If any type has no open section this course can't be scheduled
        if any(len(v) == 0 for v in byType.values()):
            return []

        combos = list(itertools_product(*[byType[t] for t in allTypes]))
        courseOptions.append(combos)

    results = []

    for schedule in itertools_product(*courseOptions):
        # Flatten: schedule is a tuple of combos; each combo is a tuple of (name, section) pairs
        sections = [pair for combo in schedule for pair in combo]

        # Check every section falls within the allowed time window
        ok = True
        for _, sec in sections:
            if sec['Start time'].time() < startTime or sec['End time'].time() > endTime:
                ok = False
                break
        if not ok:
            continue

        # Check every pair of sections for conflicts
        for i in range(len(sections)):
            if not ok:
                break
            for j in range(i + 1, len(sections)):
                _, secA = sections[i]
                _, secB = sections[j]

                # Only sections that share a weekday can conflict
                if not (set(secA['Weekends']) & set(secB['Weekends'])):
                    continue

                dtEndA   = to_dt(secA['End time'].time())
                dtStartA = to_dt(secA['Start time'].time())
                dtEndB   = to_dt(secB['End time'].time())
                dtStartB = to_dt(secB['Start time'].time())

                # No conflict only if A ends (+ gap) before B starts, or vice-versa
                if not (dtEndA + gap <= dtStartB or dtEndB + gap <= dtStartA):
                    ok = False
                    break

        if ok:
            results.append([name for name, _ in sections])

    return results

def userinput():
    print("Welcome to KC UBC Schedule matcher")


    # Enter time
    print("First, what is your start time (format: 8:00 AM)")
    start = input('> ')

    print("Second, what is your end time (format: 8:00 AM)")
    end = input('> ')
    
    print("Third, how much time do you want to make between classes, in MINUTES (e.g. 60)")
    timeBetween = int(input('> '))

    usePrev = False
    if 'coursedata.json' in os.listdir() and input('There is a previous course data saved. Use it? (y/N) ').lower().startswith('y'):
        usePrev = True

    if not usePrev:
        print("Lastly, READ THIS CAREFULLY:\n\nYou will now select the list of each course in workday saved schedule, from start to bottom (beginning with the course name)\n\nWhen you are done for a course, press ENTER, then CTRL+C ONCE.\n\nOnce you are done ALL of your courses that you want, press CTRL+C TWICE.\n\nAt any time press CTRL+Z to forcefully exit.\n\nNow begin pasting and pressing CTRL+C afterwards:\n")
        try:
            # Enter courses
            courses = []
            temp = []
            run = True
            t = True
            while run:
                try:
                    temp.append(input('>'))
                    t = True
                except KeyboardInterrupt:
                    # Twice:
                    run = t
                    t = False

                    courses.append('\n'.join(temp))
                    temp = []

                    print("\nThis course is saved. Enter the next one.\n")
            try:
                with open(os.path.join(os.getcwd(), 'coursedata.json'), 'w') as f:
                    json.dump(courses, f, indent = 4)
            except:
                print("Unable to save.")
        except:
            print_exc()
            input("\nAn error occurred. Press enter to continue... ")
    else:
        with open('coursedata.json', 'r') as f:
            courses = json.load(f)
    print("Calculating...")

    parsedCourses = []
    for i in courses:
        parsedCourses.append(parse(i))
    try:
        calced = calculate(parsedCourses, start, end, timeBetween)
    except:
        print_exc()
        print("\nAN ERROR OCCURRED, see above.")
        input('Press enter to exit... ')
        exit()

    # User-friendly print
    if len(calced) == 0:
        print("No matching courses!")
    else:
        j = 0
        for courses in calced:
            j += 1
            print(f'#{j}: {', '.join(courses)}')

def gui():
    root = tk.Tk()
    root.title("UBC Schedule Matcher")
    root.geometry("920x720")
    root.minsize(700, 520)

    course_frames = []  # list of (LabelFrame, ScrolledText)

    def _update_scrollregion(_event=None):
        courses_canvas.configure(scrollregion=courses_canvas.bbox('all'))

    def _on_canvas_resize(event):
        courses_canvas.itemconfig(inner_id, width=event.width)

    def _mousewheel(event):
        courses_canvas.yview_scroll(int(-event.delta / 120), 'units')

    def add_course(text_content=''):
        idx = len(course_frames) + 1
        frame = ttk.LabelFrame(courses_inner, text=f"Course {idx}", padding=5)
        frame.pack(fill='x', padx=6, pady=3)

        txt = scrolledtext.ScrolledText(frame, height=5, wrap='word', font=('Consolas', 9))
        txt.pack(side='left', fill='both', expand=True)
        txt.bind('<MouseWheel>', _mousewheel)
        if text_content:
            txt.insert('1.0', text_content)

        def remove(f=frame, t=txt):
            f.destroy()
            course_frames.remove((f, t))
            for i, (ff, _) in enumerate(course_frames):
                ff.config(text=f"Course {i + 1}")
            root.after(50, _update_scrollregion)

        ttk.Button(frame, text="Remove", width=8, command=remove).pack(side='right', padx=(6, 0), anchor='n')
        course_frames.append((frame, txt))
        root.after(50, _update_scrollregion)

    def load_previous():
        path = os.path.join(os.getcwd(), 'coursedata.json')
        if not os.path.exists(path):
            messagebox.showwarning("Not found", "No previous course data found in the current directory.")
            return
        with open(path) as f:
            courses = json.load(f)
        for frame, _ in list(course_frames):
            frame.destroy()
        course_frames.clear()
        for raw in courses:
            add_course(raw)
        messagebox.showinfo("Loaded", f"Loaded {len(courses)} course(s) from previous session.")

    def calculate_action():
        start = start_var.get().strip()
        end   = end_var.get().strip()
        try:
            gap_min = int(gap_var.get().strip())
        except ValueError:
            messagebox.showerror("Input error", "Min. gap must be a whole number.")
            return

        raw_courses = [t.get('1.0', 'end').strip() for _, t in course_frames]
        raw_courses = [c for c in raw_courses if c]
        if not raw_courses:
            messagebox.showerror("Input error", "Add at least one course.")
            return

        try:
            with open(os.path.join(os.getcwd(), 'coursedata.json'), 'w') as f:
                json.dump(raw_courses, f, indent=4)
        except Exception:
            pass

        parsed = [parse(c) for c in raw_courses]

        try:
            results = calculate(parsed, start, end, gap_min)
        except ValueError as e:
            messagebox.showerror("Time format error", str(e))
            return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        results_text.config(state='normal')
        results_text.delete('1.0', 'end')
        if not results:
            results_text.insert('end', "No matching schedules found.")
        else:
            for i, schedule in enumerate(results, 1):
                results_text.insert('end', f"#{i}: {', '.join(schedule)}\n")
        results_text.config(state='disabled')

    def restart():
        root.destroy()
        gui()

    ttk.Label(root, text="UBC Schedule Matcher", font=('Helvetica', 15, 'bold')).pack(pady=(12, 4))

    # Settings bar
    sf = ttk.LabelFrame(root, text="Filters", padding=10)
    sf.pack(fill='x', padx=12, pady=4)

    ttk.Label(sf, text="Start time:").grid(row=0, column=0, sticky='w')
    start_var = tk.StringVar()
    ttk.Entry(sf, textvariable=start_var, width=10).grid(row=0, column=1, padx=4)

    ttk.Label(sf, text="End time:").grid(row=0, column=2, sticky='w', padx=(14, 0))
    end_var = tk.StringVar()
    ttk.Entry(sf, textvariable=end_var, width=10).grid(row=0, column=3, padx=4)

    ttk.Label(sf, text="Min. gap between classes (min):").grid(row=0, column=4, sticky='w', padx=(14, 0))
    gap_var = tk.StringVar(value="0")
    ttk.Entry(sf, textvariable=gap_var, width=5).grid(row=0, column=5, padx=4)

    ttk.Label(sf, text='e.g. "8:00 AM" or "8 AM"', foreground='gray').grid(row=1, column=0, columnspan=4, sticky='w', pady=(3, 0))

    # Courses canvas (scrollable)
    cf = ttk.LabelFrame(root, text="Courses — paste from Workday saved schedule", padding=5)
    cf.pack(fill='both', expand=True, padx=12, pady=4)

    courses_canvas = tk.Canvas(cf, borderwidth=0, highlightthickness=0)
    vscroll = ttk.Scrollbar(cf, orient='vertical', command=courses_canvas.yview)
    courses_canvas.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side='right', fill='y')
    courses_canvas.pack(side='left', fill='both', expand=True)
    courses_canvas.bind('<MouseWheel>', _mousewheel)

    courses_inner = ttk.Frame(courses_canvas)
    inner_id = courses_canvas.create_window((0, 0), window=courses_inner, anchor='nw')
    courses_inner.bind('<Configure>', _update_scrollregion)
    courses_canvas.bind('<Configure>', _on_canvas_resize)

    # Bottom button bar
    bf = ttk.Frame(root)
    bf.pack(fill='x', padx=12, pady=4)
    ttk.Button(bf, text="+ Add Course",  command=add_course).pack(side='left')
    ttk.Button(bf, text="Load Previous", command=load_previous).pack(side='left', padx=8)
    ttk.Button(bf, text="Calculate",     command=calculate_action).pack(side='right')
    ttk.Button(bf, text="Restart",       command=restart).pack(side='right', padx=8)

    # Results
    rf = ttk.LabelFrame(root, text="Results", padding=5)
    rf.pack(fill='x', padx=12, pady=(2, 10))
    results_text = scrolledtext.ScrolledText(rf, height=9, state='disabled', wrap='word', font=('Consolas', 9))
    results_text.pack(fill='both', expand=True)

    add_course()  # one empty slot to start
    root.mainloop()


if "__main__" in __name__:
    gui()

    # CLI below: (kinda hard to use - it was for development)
    # userinput() 